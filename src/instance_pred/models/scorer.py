from dataclasses import dataclass

from .attention_indicator import AttentionIndicator

@dataclass(frozen=True, slots=True)
class ScorerConfig:
    """
    Optimized, read-only configuration used strictly for the hot loop.
    Flattened to minimize attribute lookup depth.
    """
    # Dynamics
    tau_rise: float
    tau_decay: float
    
    # Target Scores
    indicator_scores: dict[AttentionIndicator, float]

    # Thresholds
    gaze_threshold_label: int
    gaze_threshold_pos: int