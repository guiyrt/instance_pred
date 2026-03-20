from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any

from aware_protos.tern.asd.events import asd_events_pb2

from .screen_position import ScreenPosition


@dataclass(frozen=True, slots=True)
class TrackLabel:
    timestamp: datetime
    
    top_left: ScreenPosition
    width: int
    height: int

    is_visible: bool
    is_hovered: bool
    is_selected: bool
    on_pip: bool

    def is_stale(self, current_time: datetime, ttl: timedelta) -> bool:
        return (current_time - self.timestamp) > ttl

    def contains(self, p: ScreenPosition, padding: int = 0) -> bool:
        return (self.top_left.x - padding <= p.x <= self.top_left.x + self.width + padding) and \
               (self.top_left.y - padding <= p.y <= self.top_left.y + self.height + padding)

    @staticmethod
    def from_proto(payload: asd_events_pb2.TrackLabelPosition, timestamp_ms: datetime) -> "TrackLabel":
        return TrackLabel(
            timestamp=timestamp_ms,
            top_left=ScreenPosition(payload.x, payload.y),
            width=payload.width,
            height=payload.height,
            is_visible=payload.visible,
            is_hovered=payload.hovered,
            is_selected=payload.selected,
            on_pip=payload.on_pip
        )
    
    @staticmethod
    def from_row(row: tuple[Any, ...]) -> "TrackLabel":
        return TrackLabel(
            timestamp=row.timestamp_ms.to_pydatetime(),
            top_left=ScreenPosition(float(row.x), float(row.y)),
            width=int(row.width),
            height=int(row.height),
            is_visible=bool(row.visible),
            is_hovered=bool(row.hovered),
            is_selected=bool(row.selected),
            on_pip=bool(row.on_pip)
        )