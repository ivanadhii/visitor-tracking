import cv2
import gc
import os
import ctypes
import ctypes.util
import threading
import time
from typing import Optional, Dict, Any, TYPE_CHECKING

from .tracker import TrackRegistry

if TYPE_CHECKING:
    from .hls_manager import HLSWriter

_NO_AI = os.environ.get("NO_AI", "0") == "1"

if not _NO_AI:
    import torch
    from ultralytics import YOLO
    _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[Pipeline] Using device: {_DEVICE}")
else:
    _DEVICE = "cpu"

# Suppress FFmpeg global log spam via av_log_set_level(AV_LOG_ERROR=16)
_avutil = ctypes.util.find_library("avutil")
if _avutil:
    try:
        ctypes.CDLL(_avutil).av_log_set_level(16)
    except Exception:
        pass

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|stimeout;10000000|err_detect;ignore_err|fflags;discardcorrupt"
)
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

_MAX_FAILURES = 25   # consecutive failed reads before reconnect
_INFER_FPS    = 5    # YOLO inference rate
_PIPE_FPS     = 10   # annotated frames sent to FFmpeg pipe

# We keep the last annotated frame and re-send it to the pipe between
# inference ticks so FFmpeg always gets a steady stream without blank boxes.

# Bounding box / label style
_BOX_COLOR    = (0, 255, 80)    # green
_BOX_INACTIVE = (100, 100, 100) # grey for recently-inactive tracks
_FONT         = cv2.FONT_HERSHEY_SIMPLEX
_FONT_SCALE   = 0.55
_THICKNESS    = 2


def _draw_boxes(frame, results, tracker: TrackRegistry):
    """Draw YOLO bounding boxes + track tags onto frame in-place."""
    if results[0].boxes.id is None:
        return
    boxes     = results[0].boxes.xyxy.cpu().numpy().astype(int)
    track_ids = results[0].boxes.id.cpu().numpy().astype(int)
    confs     = results[0].boxes.conf.cpu().numpy()

    for (x1, y1, x2, y2), raw_tid, conf in zip(boxes, track_ids, confs):
        tid  = int(raw_tid)
        info = tracker.update(tid, float(conf))
        color = _BOX_COLOR if info.active else _BOX_INACTIVE
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, _THICKNESS)
        label = f"{info.tag} {conf:.0%}"
        (lw, lh), _ = cv2.getTextSize(label, _FONT, _FONT_SCALE, _THICKNESS)
        cv2.rectangle(frame, (x1, y1 - lh - 6), (x1 + lw + 4, y1), color, -1)
        cv2.putText(frame, label, (x1 + 2, y1 - 4),
                    _FONT, _FONT_SCALE, (0, 0, 0), _THICKNESS - 1, cv2.LINE_AA)


class StreamPipeline:
    """
    Reads RTSP, runs YOLO+ByteTrack, annotates frames, pipes to HLSWriter.
    When detection is OFF, tells HLSWriter to use direct passthrough instead.
    """

    def __init__(self, stream_id: str, url: str,
                 detection_enabled: bool = True,
                 hls_writer: Optional["HLSWriter"] = None):
        self.stream_id = stream_id
        self.url = url
        self.running = False
        self.detection_enabled = detection_enabled
        self._hls = hls_writer
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self.latest: Dict[str, Any] = {"stats": {"active_count": 0, "total_seen": 0, "tracks": []}}
        self.is_connected = False
        self.error: Optional[str] = None

        self._tracker = TrackRegistry()
        self._detection_was_enabled = detection_enabled
        self._last_infer: float = 0.0
        self._last_pipe:  float = 0.0
        self._annotated_frame: Optional[bytes] = None   # last annotated frame bytes

    # ------------------------------------------------------------------ public

    def start(self):
        self.running = True
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"pipeline-{self.stream_id}",
        )
        self._thread.start()

    def stop(self):
        self.running = False

    def get_latest(self) -> Dict[str, Any]:
        with self._lock:
            return self.latest

    # ----------------------------------------------------------------- private

    def _run(self):
        model: Optional[YOLO] = None
        cap:   Optional[cv2.VideoCapture] = None
        consecutive_failures = 0

        while self.running:
            # ── Detection OFF: release RTSP + YOLO, use HLS passthrough ─────
            if not self.detection_enabled:
                if cap:
                    cap.release()
                    cap = None
                    self.is_connected = False
                if self._detection_was_enabled:
                    model = None
                    gc.collect()
                    self._tracker = TrackRegistry()
                    self._detection_was_enabled = False
                    print(f"[Pipeline {self.stream_id}] YOLO unloaded, switching to passthrough")
                    if self._hls:
                        self._hls.start_passthrough()
                with self._lock:
                    self.latest = {"stats": {"active_count": 0, "total_seen": 0, "tracks": []}}
                time.sleep(1)
                continue

            # ── Lazy-load YOLO ───────────────────────────────────────────────
            if not _NO_AI and model is None:
                model = YOLO("yolo11n.pt")
                self._detection_was_enabled = True
                print(f"[Pipeline {self.stream_id}] YOLO loaded, switching to pipe mode")

            # ── Connect / reconnect ──────────────────────────────────────────
            if cap is None or not cap.isOpened():
                consecutive_failures = 0
                cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
                if not cap.isOpened():
                    self.is_connected = False
                    self.error = "Cannot open stream"
                    time.sleep(5)
                    continue
                self.is_connected = True
                self.error = None

            # ── Read frame ───────────────────────────────────────────────────
            time.sleep(1 / 20)
            ret, frame = cap.read()
            if not ret:
                consecutive_failures += 1
                if consecutive_failures >= _MAX_FAILURES:
                    cap.release()
                    cap = None
                    self.is_connected = False
                    consecutive_failures = 0
                continue
            consecutive_failures = 0

            # ── Resize ───────────────────────────────────────────────────────
            h, w = frame.shape[:2]
            if w > 1280:
                scale = 1280 / w
                frame = cv2.resize(frame, (1280, int(h * scale)))
                h, w = frame.shape[:2]

            now = time.time()

            # ── YOLO inference at _INFER_FPS ─────────────────────────────────
            if not _NO_AI and (now - self._last_infer) >= 1.0 / _INFER_FPS:
                self._last_infer = now
                try:
                    results = model.track(
                        frame,
                        persist=True,
                        classes=[0],
                        verbose=False,
                        device=_DEVICE,
                        tracker='/app/bytetrack.yaml',
                    )

                    active_ids: set = set()
                    if results[0].boxes.id is not None:
                        for raw_tid in results[0].boxes.id.cpu().numpy().astype(int):
                            active_ids.add(int(raw_tid))

                    _draw_boxes(frame, results, self._tracker)
                    self._tracker.mark_inactive(active_ids)

                    # Cache the freshly annotated frame bytes
                    self._annotated_frame = frame.tobytes()

                    with self._lock:
                        self.latest = {"stats": self._tracker.get_stats()}

                except Exception as exc:
                    print(f"[Pipeline {self.stream_id}] Inference error: {exc}")

            # ── Pipe to HLS writer at _PIPE_FPS ──────────────────────────────
            # Always send the last annotated frame (not the raw frame) so boxes
            # are stable between inference ticks — no flicker.
            if self._hls and (now - self._last_pipe) >= 1.0 / _PIPE_FPS:
                self._last_pipe = now
                payload = self._annotated_frame
                if payload is not None:
                    self._hls.start_pipe(w, h)
                    self._hls.write_frame(payload)

        if cap:
            cap.release()
