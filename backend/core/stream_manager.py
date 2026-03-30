import uuid
import time
import json
import os
from typing import Dict, List, Optional

from .pipeline import StreamPipeline

PERSIST_FILE = os.environ.get("STREAMS_FILE", "/app/data/streams.json")


class StreamManager:
    def __init__(self):
        self._streams: Dict[str, dict] = {}
        self._pipelines: Dict[str, StreamPipeline] = {}
        self._load()

    # ─── persistence ──────────────────────────────────────────────────────────

    def _load(self):
        if not os.path.exists(PERSIST_FILE):
            return
        try:
            with open(PERSIST_FILE) as f:
                streams = json.load(f)
            for s in streams:
                sid = s["id"]
                self._streams[sid] = s
                pipeline = StreamPipeline(sid, s["url"])
                self._pipelines[sid] = pipeline
                pipeline.start()
            print(f"[StreamManager] Restored {len(streams)} stream(s)")
        except Exception as e:
            print(f"[StreamManager] Failed to restore streams: {e}")

    def _save(self):
        os.makedirs(os.path.dirname(PERSIST_FILE), exist_ok=True)
        try:
            with open(PERSIST_FILE, "w") as f:
                json.dump(list(self._streams.values()), f)
        except Exception as e:
            print(f"[StreamManager] Failed to save streams: {e}")

    # ─── public ───────────────────────────────────────────────────────────────

    def add(self, url: str, name: str) -> str:
        sid = str(uuid.uuid4())[:8]
        self._streams[sid] = {
            "id": sid,
            "url": url,
            "name": name,
            "created_at": time.time(),
        }
        pipeline = StreamPipeline(sid, url)
        self._pipelines[sid] = pipeline
        pipeline.start()
        self._save()
        return sid

    def remove(self, sid: str) -> bool:
        if sid not in self._streams:
            return False
        if sid in self._pipelines:
            self._pipelines[sid].stop()
            del self._pipelines[sid]
        del self._streams[sid]
        self._save()
        return True

    def list_streams(self) -> List[dict]:
        result = []
        for sid, stream in self._streams.items():
            data = dict(stream)
            p = self._pipelines.get(sid)
            data["connected"] = p.is_connected if p else False
            data["error"] = p.error if p else None
            data["stats"] = (p.latest or {}).get("stats", {}) if p else {}
            result.append(data)
        return result

    def get_pipeline(self, sid: str) -> Optional[StreamPipeline]:
        return self._pipelines.get(sid)
