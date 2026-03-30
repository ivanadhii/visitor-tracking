import uuid
import time
import yaml
import os
import threading
from typing import Dict, List, Optional

from .pipeline import StreamPipeline

STREAMS_FILE = os.environ.get("STREAMS_FILE", "/app/data/streams.yaml")


class StreamManager:
    def __init__(self):
        self._streams: Dict[str, dict] = {}
        self._pipelines: Dict[str, StreamPipeline] = {}
        self._file_mtime: float = 0
        self._lock = threading.Lock()

        self._load_from_file()
        self._start_watcher()

    # ─── file I/O ─────────────────────────────────────────────────────────────

    def _read_yaml(self) -> List[dict]:
        if not os.path.exists(STREAMS_FILE):
            return []
        try:
            with open(STREAMS_FILE) as f:
                data = yaml.safe_load(f) or {}
            return data.get("streams", []) or []
        except Exception as e:
            print(f"[StreamManager] Failed to read YAML: {e}")
            return []

    def _write_yaml(self):
        os.makedirs(os.path.dirname(STREAMS_FILE), exist_ok=True)
        streams_list = [
            {"id": s["id"], "name": s["name"], "url": s["url"], "detection": s.get("detection", True)}
            for s in self._streams.values()
        ]
        try:
            with open(STREAMS_FILE, "w") as f:
                yaml.dump(
                    {"streams": streams_list},
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
            self._file_mtime = os.path.getmtime(STREAMS_FILE)
        except Exception as e:
            print(f"[StreamManager] Failed to write YAML: {e}")

    def _load_from_file(self):
        entries = self._read_yaml()
        for entry in entries:
            sid = entry.get("id") or str(uuid.uuid4())[:8]
            url = entry.get("url", "").strip()
            name = entry.get("name", f"Camera {sid}")
            detection = entry.get("detection", True)
            if not url:
                continue
            self._streams[sid] = {
                "id": sid,
                "url": url,
                "name": name,
                "detection": detection,
                "created_at": entry.get("created_at", time.time()),
            }
            pipeline = StreamPipeline(sid, url, detection_enabled=detection)
            self._pipelines[sid] = pipeline
            pipeline.start()
        if os.path.exists(STREAMS_FILE):
            self._file_mtime = os.path.getmtime(STREAMS_FILE)
        print(f"[StreamManager] Loaded {len(self._streams)} stream(s) from {STREAMS_FILE}")

    # ─── file watcher ─────────────────────────────────────────────────────────

    def _start_watcher(self):
        t = threading.Thread(
            target=self._watch_loop, daemon=True, name="stream-watcher"
        )
        t.start()

    def _watch_loop(self):
        while True:
            time.sleep(3)
            try:
                if not os.path.exists(STREAMS_FILE):
                    continue
                mtime = os.path.getmtime(STREAMS_FILE)
                if mtime > self._file_mtime:
                    self._file_mtime = mtime
                    self._sync_from_file()
            except Exception as e:
                print(f"[StreamManager] Watcher error: {e}")

    def _sync_from_file(self):
        entries = self._read_yaml()
        file_streams: Dict[str, dict] = {}
        for entry in entries:
            sid = entry.get("id") or str(uuid.uuid4())[:8]
            url = entry.get("url", "").strip()
            name = entry.get("name", f"Camera {sid}")
            detection = entry.get("detection", True)
            if url:
                file_streams[sid] = {
                    "id": sid,
                    "url": url,
                    "name": name,
                    "detection": detection,
                    "created_at": entry.get("created_at", time.time()),
                }

        with self._lock:
            current_ids = set(self._streams.keys())
            file_ids = set(file_streams.keys())

            # Streams added in file
            for sid in file_ids - current_ids:
                s = file_streams[sid]
                self._streams[sid] = s
                pipeline = StreamPipeline(sid, s["url"], detection_enabled=s.get("detection", True))
                self._pipelines[sid] = pipeline
                pipeline.start()
                print(f"[StreamManager] Auto-added '{s['name']}' from file")

            # Streams removed from file
            for sid in current_ids - file_ids:
                name = self._streams[sid]["name"]
                if sid in self._pipelines:
                    self._pipelines[sid].stop()
                    del self._pipelines[sid]
                del self._streams[sid]
                print(f"[StreamManager] Auto-removed '{name}' (deleted from file)")

            # URL, name, or detection changed
            for sid in current_ids & file_ids:
                current = self._streams[sid]
                updated = file_streams[sid]
                if current["url"] != updated["url"]:
                    if sid in self._pipelines:
                        self._pipelines[sid].stop()
                    self._streams[sid] = updated
                    pipeline = StreamPipeline(sid, updated["url"], detection_enabled=updated.get("detection", True))
                    self._pipelines[sid] = pipeline
                    pipeline.start()
                    print(f"[StreamManager] Updated URL for '{updated['name']}'")
                else:
                    if current["name"] != updated["name"]:
                        self._streams[sid]["name"] = updated["name"]
                        print(f"[StreamManager] Renamed stream to '{updated['name']}'")
                    if current.get("detection", True) != updated.get("detection", True):
                        self._streams[sid]["detection"] = updated["detection"]
                        if sid in self._pipelines:
                            self._pipelines[sid].detection_enabled = updated["detection"]
                        print(f"[StreamManager] Detection {'ON' if updated['detection'] else 'OFF'} for '{updated['name']}'")

    # ─── public ───────────────────────────────────────────────────────────────

    def add(self, url: str, name: str) -> str:
        sid = str(uuid.uuid4())[:8]
        with self._lock:
            self._streams[sid] = {
                "id": sid,
                "url": url,
                "name": name,
                "detection": True,
                "created_at": time.time(),
            }
            pipeline = StreamPipeline(sid, url, detection_enabled=True)
            self._pipelines[sid] = pipeline
            pipeline.start()
            self._write_yaml()
        return sid

    def set_detection_all(self, enabled: bool):
        with self._lock:
            for sid in self._streams:
                self._streams[sid]["detection"] = enabled
                if sid in self._pipelines:
                    self._pipelines[sid].detection_enabled = enabled
            self._write_yaml()

    def set_detection(self, sid: str, enabled: bool) -> bool:
        with self._lock:
            if sid not in self._streams:
                return False
            self._streams[sid]["detection"] = enabled
            if sid in self._pipelines:
                self._pipelines[sid].detection_enabled = enabled
            self._write_yaml()
        return True

    def remove(self, sid: str) -> bool:
        with self._lock:
            if sid not in self._streams:
                return False
            if sid in self._pipelines:
                self._pipelines[sid].stop()
                del self._pipelines[sid]
            del self._streams[sid]
            self._write_yaml()
        return True

    def list_streams(self) -> List[dict]:
        with self._lock:
            result = []
            for sid, stream in self._streams.items():
                data = dict(stream)
                p = self._pipelines.get(sid)
                data["connected"] = p.is_connected if p else False
                data["error"] = p.error if p else None
                data["stats"] = (p.latest or {}).get("stats", {}) if p else {}
                data["detection"] = stream.get("detection", True)
                result.append(data)
        return result

    def get_pipeline(self, sid: str) -> Optional[StreamPipeline]:
        with self._lock:
            return self._pipelines.get(sid)
