import time
from dataclasses import dataclass, field
from typing import Dict, List

# A track is considered inactive only after this many seconds without detection.
# Prevents blinking when a frame is dropped or HEVC decoding hiccups.
_INACTIVE_GRACE_SEC = 2.0


@dataclass
class TrackInfo:
    tag: str
    track_id: int
    first_seen: float
    last_seen: float
    active: bool = True
    confidence: float = 0.0


class TrackRegistry:
    """Assigns persistent human-readable tags to ByteTrack track IDs."""

    def __init__(self):
        self._registry: Dict[int, TrackInfo] = {}
        self._counter = 0

    def update(self, track_id: int, confidence: float) -> TrackInfo:
        now = time.time()
        if track_id not in self._registry:
            self._counter += 1
            self._registry[track_id] = TrackInfo(
                tag=f"Person_{self._counter:03d}",
                track_id=track_id,
                first_seen=now,
                last_seen=now,
                confidence=confidence,
            )
        else:
            info = self._registry[track_id]
            info.last_seen = now
            info.confidence = confidence
            info.active = True
        return self._registry[track_id]

    def mark_inactive(self, active_ids: set):
        """Mark tracks not seen recently as inactive, with a grace period."""
        now = time.time()
        for track_id, info in self._registry.items():
            if track_id in active_ids:
                info.active = True
            elif info.active and (now - info.last_seen) >= _INACTIVE_GRACE_SEC:
                info.active = False

    def get_stats(self) -> dict:
        tracks = list(self._registry.values())
        return {
            "active_count": sum(1 for t in tracks if t.active),
            "total_seen": len(tracks),
            "tracks": [
                {
                    "tag": t.tag,
                    "track_id": t.track_id,
                    "active": t.active,
                    "first_seen": t.first_seen,
                    "last_seen": t.last_seen,
                    "confidence": t.confidence,
                }
                for t in tracks
            ],
        }
