from datetime import datetime
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aware_protos.tern.asd.events import asd_events_pb2


class PopupMenu(StrEnum):
    CFLMenu = "CFLMenu"
    HeadingMenu = "HeadingMenu"
    WaypointMenu = "WaypointMenu"


@dataclass(frozen=True, slots=True)
class Popup:
    timestamp: datetime
    callsign: str
    menu: PopupMenu

    def __repr__(self):
        return f"[{self.menu.value}|{self.callsign}]"

    @staticmethod
    def from_proto(event: asd_events_pb2.Popup, timestamp_ms: datetime) -> "Popup":
        return Popup(
            timestamp=timestamp_ms,
            callsign=event.flight_id.callsign,
            menu=PopupMenu(event.name)
        )
    
    @staticmethod
    def from_row(row: tuple[Any, ...]) -> "Popup":
        return Popup(
            timestamp=row.timestamp_ms.to_pydatetime(),
            callsign=row.callsign,
            menu=PopupMenu(row.name)
        )