from typing import Final

from ..models import ScreenPosition


class GazeState:
    __slots__ = ("pos", "is_fixating", "_last_update_ms")

    # Constants
    MAX_FIXATION_PX_SEC: Final[float] = 240.0
    _MAX_DT_SEC: Final[float] = 0.5
    
    def __init__(self):
        self.pos: ScreenPosition | None = None
        self.is_fixating: bool = False
        self._last_update_ms = 0.0

    @property
    def has_signal(self) -> bool:
        return self.pos is not None

    def update(self, x: float | None, y: float | None, timestamp_ms: float) -> None:
        dt_sec = (timestamp_ms - self._last_update_ms) / 1000.0
        
        # Skip duplicates or out-of-order packets
        if dt_sec <= 0:
            return

        # Determine new position (Handle Blink/NaN)
        new_pos = ScreenPosition(x, y) if (x is not None and y is not None) else None

        # Check continuity (current and past positions are valid and within _MAX_DT_SEC time gap)
        is_continuous = (
            new_pos is not None and 
            self.pos is not None and 
            dt_sec <= self._MAX_DT_SEC
        )

        if is_continuous:
            velocity_px_sec = new_pos.dist(self.pos) / dt_sec
            self.is_fixating = velocity_px_sec <= self.MAX_FIXATION_PX_SEC
        else:
            self.is_fixating = False

        self.pos = new_pos
        self._last_update_ms = timestamp_ms