from enum import Enum
from dataclasses import dataclass
from typing import Any

class EventType(Enum):
    GAZE = "gaze"
    MOUSE_POSITION = "mouse_position"
    TRACK_LABEL_POSITION = "track_label_position"
    TRACK_SCREEN_POSITION = "track_screen_position"
    CLEARANCE = "clearance"
    POPUP = "popup"
    TRANSFER = "transfer"
    SEP_TOOL = "sep_tool"
    DISTANCE_MEASUREMENT = "distance_measurement"
    SPEED_VECTOR = "speed_vector"
    TRACK_MARK = "track_mark"
    ROUTE_INTERACTION = "route_interaction"
    KEYBOARD_SHORTCUT = "keyboard_shortcut"
    

@dataclass(frozen=True, slots=True)
class RowEvent:
    type: EventType
    timestamp_ms: float
    data: tuple[Any, ...]