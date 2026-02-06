from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class ScoredAircraft:
    callsign: str
    score: float

    def __repr__(self):
        return f"Callsign: {self.callsign}, Score: {self.score}"

@dataclass(frozen=True, slots=True)
class InstancePrediction:
    timestamp_ms: float
    aircraft: ScoredAircraft | None
    candidates: list[ScoredAircraft] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.aircraft is not None