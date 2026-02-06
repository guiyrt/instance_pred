from dataclasses import dataclass

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
    s_popup_opened: float
    s_label_selected: float
    s_label_hovered: float
    s_label_parked: float
    s_dist_measurement: float
    s_fixation_label: float
    s_fixation_pos: float

    # Thresholds
    gaze_threshold_label: int
    gaze_threshold_pos: int