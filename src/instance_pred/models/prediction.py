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
    timestamp: datetime
    primary_target: ScoredAircraft | None
    candidates: list[ScoredAircraft] = field(default_factory=list)