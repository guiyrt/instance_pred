from enum import IntEnum

class AttentionIndicator(IntEnum):
    """
    Core Domain Enum representing visual attention heuristics.
    Values map 1:1 to zhaw.protobuf.AircraftAttentionTarget.AttentionIndicator
    """
    POPUP_OPENED = 1
    LABEL_SELECTED = 2
    LABEL_HOVERED = 3
    LABEL_PARKED = 4
    LABEL_FIXATION = 5
    AIRCRAFT_FIXATION = 6
    DIST_MEASUREMENT = 7