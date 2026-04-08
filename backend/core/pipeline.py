import cv2
import gc
import os
import ctypes
import ctypes.util
import threading
import time
from typing import Optional, Dict, Any

from .tracker import TrackRegistry

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


class StreamPipeline:
    """
    AI detection pipeline: reads RTSP, runs YOLO+ByteTrack, stores stats.
    Video delivery is handled separately by HLSStream (FFmpeg).
    Pipeline only connects to RTSP when detection is enabled.
    """

    def __init__(self, stream_id: str, url: str, detection_enabled: bool = True):
        self.stream_id = stream_id
        self.url = url
        self.running = False
        self.detection_enabled = detection_enabled
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self.latest: Optional[Dict[str, Any]] = None
        self.is_connected = False
        self.error: Optional[str] = None

        self._tracker = TrackRegistry()
        self._detection_was_enabled = detection_enabled

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

    def get_latest(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.latest

    # ----------------------------------------------------------------- private

    def _run(self):
        model: Optional[YOLO] = None
        cap: Optional[cv2.VideoCapture] = None
        consecutive_failures = 0

        while self.running:
            # ── Detection off: release RTSP, sleep, no AI ───────────────────
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
                    print(f"[Pipeline {self.stream_id}] YOLO unloaded")
                with self._lock:
                    self.latest = {"stats": {"active_count": 0, "total_count": 0, "persons": []}}
                time.sleep(1)
                continue

            # ── Lazy-load YOLO ───────────────────────────────────────────────
            if not _NO_AI and model is None:
                model = YOLO("yolov8n.pt")
                self._detection_was_enabled = True

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

            # ── Read frame ──────────────────────────────────────────────────
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

            try:
                h, w = frame.shape[:2]
                if w > 1280:
                    scale = 1280 / w
                    frame = cv2.resize(frame, (1280, int(h * scale)))

                stats = {"active_count": 0, "total_count": 0, "persons": []}

                if not _NO_AI:
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
                        track_ids = results[0].boxes.id.cpu().numpy().astype(int)
                        confs = results[0].boxes.conf.cpu().numpy()
                        for raw_tid, conf in zip(track_ids, confs):
                            tid = int(raw_tid)
                            self._tracker.update(tid, float(conf))
                            active_ids.add(tid)

                    self._tracker.mark_inactive(active_ids)
                    stats = self._tracker.get_stats()

                with self._lock:
                    self.latest = {"stats": stats}

            except Exception as exc:
                print(f"[Pipeline {self.stream_id}] Error: {exc}")

        if cap:
            cap.release()
