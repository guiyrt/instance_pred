from ..models import ScreenPosition
from ..types import UninitializedToken, _UNINITIALIZED

class MouseState:
    __slots__ = ('_pos', '_last_update_ms')

    IDLE_THRESHOLD_MS = 2000

    def __init__(self):
        self._pos: ScreenPosition | UninitializedToken = _UNINITIALIZED
        self._last_update_ms = -1.0

    @property
    def pos(self) -> ScreenPosition | UninitializedToken:
        return self._pos

    @property
    def is_active(self) -> bool:
        return self._pos is not _UNINITIALIZED

    def is_idle(self, current_time_ms: float) -> bool:
        return not self.is_active or (current_time_ms - self._last_update_ms > self.IDLE_THRESHOLD_MS)

    def update(self, x: float, y: float, timestamp_ms: float) -> None:
        if timestamp_ms <= self._last_update_ms:
            return

        self._pos = ScreenPosition(x, y)
        self._last_update_ms = timestamp_ms