from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any

from aware_protos.tern.asd.events import asd_events_pb2

from .screen_position import ScreenPosition


@dataclass(frozen=True, slots=True)
class TrackPos:
    timestamp: datetime
    pos: ScreenPosition
    is_visible: bool

    def is_stale(self, current_time: datetime, ttl: timedelta) -> bool:
        return (current_time - self.timestamp) > ttl
    
    @staticmethod
    def from_proto(payload: asd_events_pb2.TrackScreenPosition, timestamp_ms: datetime) -> "TrackPos":
        return TrackPos(
            timestamp=timestamp_ms,
            pos=ScreenPosition(payload.x, payload.y),
            is_visible=payload.visible
        )
    
    @staticmethod
    def from_row(row: tuple[Any, ...]) -> "TrackPos":
        return TrackPos(
            timestamp=row.timestamp_ms.to_pydatetime(),
            pos=ScreenPosition(float(row.x), float(row.y)),
            is_visible=bool(row.visible),
        )