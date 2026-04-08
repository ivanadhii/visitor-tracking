import os
import shutil
import subprocess
import threading
import time
from typing import Optional

HLS_DIR = os.environ.get("HLS_DIR", "/app/hls")


class HLSWriter:
    """
    Receives raw BGR frames from the pipeline and pipes them into FFmpeg,
    which encodes to H.264 and writes HLS segments.

    When detection is OFF the pipeline does not produce frames, so this
    writer falls back to a direct RTSP→HLS FFmpeg process (no annotation).
    """

    def __init__(self, stream_id: str, url: str):
        self.stream_id = stream_id
        self.url = url
        self._out_dir = os.path.join(HLS_DIR, stream_id)
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._width = 0
        self._height = 0
        self._mode = "none"   # "pipe" | "passthrough"
        self._passthrough_thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def playlist_path(self) -> str:
        return os.path.join(self._out_dir, "index.m3u8")

    @property
    def active(self) -> bool:
        try:
            return (time.time() - os.path.getmtime(self.playlist_path)) < 10
        except OSError:
            return False

    # ── public ────────────────────────────────────────────────────────────────

    def start_passthrough(self):
        """Start FFmpeg reading directly from RTSP (detection OFF)."""
        with self._lock:
            if self._mode == "passthrough" and self._proc and self._proc.poll() is None:
                return
            self._stop_proc()
            self._mode = "passthrough"
            self._running = True
        self._passthrough_thread = threading.Thread(
            target=self._run_passthrough, daemon=True,
            name=f"hls-pass-{self.stream_id}"
        )
        self._passthrough_thread.start()

    def start_pipe(self, width: int, height: int):
        """Start FFmpeg reading raw BGR frames from stdin (detection ON)."""
        with self._lock:
            if (self._mode == "pipe"
                    and self._proc and self._proc.poll() is None
                    and self._width == width and self._height == height):
                return
            self._stop_proc()
            self._width = width
            self._height = height
            self._mode = "pipe"
            os.makedirs(self._out_dir, exist_ok=True)
            cmd = self._pipe_cmd(width, height)
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def write_frame(self, bgr_bytes: bytes) -> bool:
        """Write one raw BGR frame to the FFmpeg pipe. Returns False if pipe is dead."""
        with self._lock:
            if self._mode != "pipe" or not self._proc or self._proc.poll() is not None:
                return False
            try:
                self._proc.stdin.write(bgr_bytes)
                return True
            except (BrokenPipeError, OSError):
                return False

    def stop(self):
        self._running = False
        with self._lock:
            self._stop_proc()
        shutil.rmtree(self._out_dir, ignore_errors=True)

    # ── private ───────────────────────────────────────────────────────────────

    def _stop_proc(self):
        """Must be called with self._lock held."""
        if self._proc:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
            except OSError:
                pass
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
        self._mode = "none"

    def _hls_output_args(self) -> list:
        seg_path = os.path.join(self._out_dir, "seg%d.ts")
        return [
            "-f", "hls",
            "-hls_time", "1",
            "-hls_list_size", "5",
            "-hls_flags", "delete_segments+independent_segments",
            "-hls_segment_filename", seg_path,
            self.playlist_path,
        ]

    def _pipe_cmd(self, width: int, height: int) -> list:
        return [
            "ffmpeg", "-loglevel", "error",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}",
            "-r", "10",           # pipeline writes ~10fps annotated frames
            "-i", "pipe:0",
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-b:v", "1500k", "-g", "10", "-sc_threshold", "0",
            "-pix_fmt", "yuv420p",
            *self._hls_output_args(),
        ]

    def _passthrough_cmd(self) -> list:
        return [
            "ffmpeg", "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-stimeout", "10000000",
            "-i", self.url,
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-b:v", "1500k", "-g", "25", "-sc_threshold", "0",
            "-an",
            *self._hls_output_args(),
        ]

    def _run_passthrough(self):
        os.makedirs(self._out_dir, exist_ok=True)
        while self._running:
            with self._lock:
                if self._mode != "passthrough":
                    break
                cmd = self._passthrough_cmd()
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            self._proc.wait()
            if self._running and self._mode == "passthrough":
                print(f"[HLS {self.stream_id}] Passthrough restarting in 3s…")
                time.sleep(3)


class HLSManager:
    def __init__(self):
        self._writers: dict[str, HLSWriter] = {}
        os.makedirs(HLS_DIR, exist_ok=True)

    def add(self, stream_id: str, url: str) -> HLSWriter:
        if stream_id not in self._writers:
            w = HLSWriter(stream_id, url)
            self._writers[stream_id] = w
        return self._writers[stream_id]

    def get(self, stream_id: str) -> Optional[HLSWriter]:
        return self._writers.get(stream_id)

    def remove(self, stream_id: str):
        w = self._writers.pop(stream_id, None)
        if w:
            w.stop()

    def is_active(self, stream_id: str) -> bool:
        w = self._writers.get(stream_id)
        return w.active if w else False

    def restart(self, stream_id: str, url: str):
        self.remove(stream_id)
        self.add(stream_id, url)
