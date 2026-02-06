from dataclasses import dataclass
from enum import Enum
from typing import Any

from aware_protos.tern.asd.events import asd_events_pb2


class PopupMenu(Enum):
    CFLMenu = "CFLMenu"
    HeadingMenu = "HeadingMenu"
    WaypointMenu = "WaypointMenu"


@dataclass(frozen=True, slots=True)
class Popup:
    timestamp_ms: float
    callsign: str
    menu: PopupMenu

    def __repr__(self):
        return f"[{self.menu.value}|{self.callsign}]"

    @staticmethod
    def from_proto(event: asd_events_pb2.Popup, timestamp_ms: int) -> "Popup":
        return Popup(
            timestamp_ms=timestamp_ms,
            callsign=event.flight_id.callsign,
            menu=PopupMenu(event.name)
        )
    
    @staticmethod
    def from_row(row: tuple[Any, ...]) -> "Popup":
        return Popup(
            timestamp_ms=int(row.epoch_ms),
            callsign=row.callsign,
            menu=PopupMenu(row.name)
        )