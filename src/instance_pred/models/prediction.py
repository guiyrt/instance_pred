from datetime import datetime
from dataclasses import dataclass, field

from .attention_indicator import AttentionIndicator

@dataclass(frozen=True, slots=True)
class ScoredAircraft:
    callsign: str
    score: float
    indicators: tuple[AttentionIndicator]

    def __repr__(self):
        return f"Callsign: {self.callsign}, Score: {self.score}"

@dataclass(frozen=True, slots=True)
class InstancePrediction:
    timestamp_ms: datetime
    aircraft: ScoredAircraft | None
    candidates: list[ScoredAircraft] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.aircraft is not None