from dataclasses import dataclass
import math

@dataclass(frozen=True, slots=True)
class ScreenPosition:
    x: float
    y: float

    def dist(self, other: "ScreenPosition") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)