from dataclasses import dataclass
from typing import Any

from aware_protos.tern.asd.events import asd_events_pb2

from .screen_position import ScreenPosition


@dataclass(frozen=True, slots=True)
class TrackPos:
    timestamp_ms: float
    pos: ScreenPosition
    is_visible: bool

    def is_stale(self, current_time_ms: float, ttl: int) -> bool:
        return (current_time_ms - self.timestamp_ms) > ttl
    
    @staticmethod
    def from_proto(payload: asd_events_pb2.TrackScreenPosition, timestamp_ms: int) -> "TrackPos":
        return TrackPos(
            timestamp_ms=timestamp_ms,
            pos=ScreenPosition(payload.x, payload.y),
            is_visible=payload.visible
        )
    
    @staticmethod
    def from_row(row: tuple[Any, ...]) -> "TrackPos":
        return TrackPos(
            timestamp_ms=int(row.epoch_ms),
            pos=ScreenPosition(float(row.x), float(row.y)),
            is_visible=bool(row.visible),
        )