import cv2
import gc
import os
import base64
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

_FRAME_INTERVAL_OFF = 1 / 10   # 10 fps when detection is off
_FRAME_INTERVAL_ON  = 1 / 20   # 20 fps cap when detection is on

# Force TCP transport for RTSP — avoids UDP packet loss that causes
# H.265 "Could not find ref with POC" / missing reference frame errors.
# Also discard corrupt packets instead of propagating decode errors.
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|stimeout;5000000|fflags;discardcorrupt"
)


class StreamPipeline:
    """
    Runs RTSP capture + YOLOv8 person detection + ByteTrack in a background thread.
    Stores the latest annotated frame + stats for WebSocket consumers to poll.
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

        while self.running:
            # ── Model lifecycle ──────────────────────────────────────────────
            if not _NO_AI and self.detection_enabled and model is None:
                model = YOLO("yolov8n.pt")
                self._detection_was_enabled = True
            elif not self.detection_enabled and self._detection_was_enabled:
                model = None
                gc.collect()
                self._tracker = TrackRegistry()
                self._detection_was_enabled = False
                print(f"[Pipeline {self.stream_id}] YOLO unloaded")

            # ── Connect / reconnect ──────────────────────────────────────────
            if cap is None or not cap.isOpened():
                cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if not cap.isOpened():
                    self.is_connected = False
                    self.error = "Cannot open stream"
                    time.sleep(3)
                    continue
                self.is_connected = True
                self.error = None

            # ── Throttle: sleep first, then read ONE frame ───────────────────
            # This is the key: sleep lets the OS scheduler rest this thread
            # instead of burning CPU in a tight loop.
            if self.detection_enabled:
                time.sleep(_FRAME_INTERVAL_ON)
            else:
                time.sleep(_FRAME_INTERVAL_OFF)

            ret, frame = cap.read()
            if not ret:
                cap.release()
                cap = None
                self.is_connected = False
                continue

            try:
                h, w = frame.shape[:2]
                if w > 1280:
                    scale = 1280 / w
                    display_frame = cv2.resize(frame, (1280, int(h * scale)))
                else:
                    display_frame = frame.copy()

                if not _NO_AI and self.detection_enabled:
                    results = model.track(
                        display_frame,
                        persist=True,
                        classes=[0],
                        verbose=False,
                        device=_DEVICE,
                        tracker='/app/bytetrack.yaml',
                    )

                    active_ids: set = set()

                    if results[0].boxes.id is not None:
                        boxes = results[0].boxes.xyxy.cpu().numpy()
                        track_ids = results[0].boxes.id.cpu().numpy().astype(int)
                        confs = results[0].boxes.conf.cpu().numpy()

                        for box, raw_tid, conf in zip(boxes, track_ids, confs):
                            tid = int(raw_tid)
                            info = self._tracker.update(tid, float(conf))
                            active_ids.add(tid)

                            x1, y1, x2, y2 = map(int, box)
                            color = (0, 255, 100)
                            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)

                            label = info.tag
                            (tw, th), _ = cv2.getTextSize(
                                label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2
                            )
                            cv2.rectangle(
                                display_frame,
                                (x1, y1 - th - 10),
                                (x1 + tw + 6, y1),
                                color,
                                -1,
                            )
                            cv2.putText(
                                display_frame,
                                label,
                                (x1 + 3, y1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.55,
                                (0, 0, 0),
                                2,
                            )

                    self._tracker.mark_inactive(active_ids)
                    stats = self._tracker.get_stats()
                else:
                    stats = {"active_count": 0, "total_count": 0, "persons": []}

                _, buf = cv2.imencode(
                    ".jpg", display_frame, [cv2.IMWRITE_JPEG_QUALITY, 75]
                )
                frame_b64 = base64.b64encode(buf).decode("utf-8")

                with self._lock:
                    self.latest = {"frame": frame_b64, "stats": stats}

            except Exception as exc:
                print(f"[Pipeline {self.stream_id}] Error: {exc}")

        if cap:
            cap.release()
