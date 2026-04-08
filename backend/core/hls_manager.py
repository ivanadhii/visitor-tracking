import os
import shutil
import subprocess
import threading
import time
from typing import Dict, Optional

HLS_DIR = os.environ.get("HLS_DIR", "/app/hls")

# Transcode to H.264 for universal browser support, or copy H.265 as-is.
# libx264 ultrafast has minimal CPU overhead and works on all browsers.
# Set TRANSCODE_HLS=0 to use copy mode (lighter but requires browser H.265 support).
_TRANSCODE = os.environ.get("TRANSCODE_HLS", "1") == "1"


class HLSStream:
    """Manages a single FFmpeg process that converts RTSP → HLS segments."""

    def __init__(self, stream_id: str, url: str):
        self.stream_id = stream_id
        self.url = url
        self.running = False
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._out_dir = os.path.join(HLS_DIR, stream_id)

    @property
    def playlist_path(self) -> str:
        return os.path.join(self._out_dir, "index.m3u8")

    @property
    def active(self) -> bool:
        """True if playlist exists and was written in the last 10 seconds."""
        try:
            return (time.time() - os.path.getmtime(self.playlist_path)) < 10
        except OSError:
            return False

    def start(self):
        self.running = True
        os.makedirs(self._out_dir, exist_ok=True)
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"hls-{self.stream_id}"
        )
        self._thread.start()

    def stop(self):
        self.running = False
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        shutil.rmtree(self._out_dir, ignore_errors=True)

    def _build_cmd(self) -> list:
        seg_path = os.path.join(self._out_dir, "seg%d.ts")

        video_opts = (
            ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
             "-b:v", "1500k", "-g", "25", "-sc_threshold", "0"]
            if _TRANSCODE else
            ["-c:v", "copy"]
        )

        return [
            "ffmpeg",
            "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-stimeout", "10000000",
            "-i", self.url,
            *video_opts,
            "-an",
            "-f", "hls",
            "-hls_time", "1",
            "-hls_list_size", "5",
            "-hls_flags", "delete_segments+independent_segments",
            "-hls_segment_filename", seg_path,
            self.playlist_path,
        ]

    def _run(self):
        while self.running:
            try:
                self._proc = subprocess.Popen(
                    self._build_cmd(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._proc.wait()
            except Exception as e:
                print(f"[HLS {self.stream_id}] Error: {e}")

            if self.running:
                print(f"[HLS {self.stream_id}] Restarting in 3s…")
                time.sleep(3)


class HLSManager:
    def __init__(self):
        self._streams: Dict[str, HLSStream] = {}
        os.makedirs(HLS_DIR, exist_ok=True)

    def add(self, stream_id: str, url: str):
        if stream_id in self._streams:
            return
        s = HLSStream(stream_id, url)
        self._streams[stream_id] = s
        s.start()

    def remove(self, stream_id: str):
        s = self._streams.pop(stream_id, None)
        if s:
            s.stop()

    def is_active(self, stream_id: str) -> bool:
        s = self._streams.get(stream_id)
        return s.active if s else False

    def restart(self, stream_id: str, url: str):
        self.remove(stream_id)
        self.add(stream_id, url)
