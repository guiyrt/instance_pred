from datetime import datetime, timedelta

from ..models import ScreenPosition
from ..types import UninitializedToken, _UNINITIALIZED

class MouseState:
    __slots__ = ('_pos', '_last_update')

    IDLE_THRESHOLD: timedelta = timedelta(seconds=2)

    def __init__(self):
        self._pos: ScreenPosition | UninitializedToken = _UNINITIALIZED
        self._last_update: datetime | None = None

    @property
    def pos(self) -> ScreenPosition | UninitializedToken:
        return self._pos

    @property
    def is_active(self) -> bool:
        return self._pos is not _UNINITIALIZED and self._last_update is not None

    def is_idle(self, current_time: datetime) -> bool:
        return not self.is_active or (current_time - self._last_update > self.IDLE_THRESHOLD)

    def update(self, x: float, y: float, current_time: datetime) -> None:
        if self._last_update is not None and current_time <= self._last_update:
            return

        self._pos = ScreenPosition(x, y)
        self._last_update = current_time