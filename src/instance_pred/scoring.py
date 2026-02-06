import math

from .states import WorldState, AircraftState
from .models import InstancePrediction, ScoredAircraft, ScorerConfig

class HeuristicScorer:
    """
    Stateful scoring engine.
    Maintains the current score for every aircraft and updates it based on
    the passage of time (dt) and the state of the World.
    """
    def __init__(self, config: ScorerConfig) -> None:
        self.cfg = config
        
        # { callsign: <value> }
        self.scores: dict[str, float] = {}
        self.targets: dict[str, float] = {}
        
        # Track time to calculate internal dt
        self.last_tick_time: float = 0.0
    
    def get_prediction(self) -> InstancePrediction:
        values: list[ScoredAircraft] = sorted(
            filter(
                lambda x: x.score > 1.0,
                (ScoredAircraft(callsign, score) for callsign, score in self.scores.items()),
            ),
            key=lambda x: x.score,
            reverse=True
        )

        return InstancePrediction(
            self.last_tick_time,
            values[0] if values else None,
            values
        )
    
    def _apply_alpha_filter(self, current: float, target: float, dt_s: float) -> float:
        r"""
        Calculates the new score based on the Time Independent formulation.
        
        The formula is:
        
        .. math::
            \alpha = 1 - e^{-\frac{\Delta t}{\tau}}
            
            S_{new} = S_{old} + (S_{target} - S_{old}) \cdot \alpha

        Where :math:`\tau` is either `RISE_TIME` (if target > current) or `DECAY_TIME` (if target <= current).
        """
        if dt_s <= 0:
            return current

        tau = self.cfg.tau_rise if target > current else self.cfg.tau_decay    
        alpha = 1.0 - math.exp(-dt_s / tau)
        
        return current + (target - current) * alpha

    def _calculate_target(self, aircraft: AircraftState, state: WorldState, is_mouse_idle: bool) -> float:
        scores = [0]

        # Pop-up
        if state.popup is not None and aircraft.callsign == state.popup.callsign:
            scores.append(self.cfg.s_popup_opened)

        # Label
        if aircraft.track_label is not None:
            # Interacting with label
            if aircraft.track_label.is_selected:
                scores.append(self.cfg.s_label_selected)

            # Mouse hovering on label
            if aircraft.track_label.is_hovered:
                scores.append(
                    self.cfg.s_label_hovered
                    if not is_mouse_idle
                    else self.cfg.s_label_parked
                )

        # Gaze
        if state.gaze.has_signal and state.gaze.is_fixating:
            # Looking at label
            if aircraft.track_label is not None and aircraft.track_label.contains(state.gaze.pos, self.cfg.gaze_threshold_label):
                scores.append(self.cfg.s_fixation_label)

            # Looking at aircraft
            if aircraft.track_pos is not None and aircraft.track_pos.pos.dist(state.gaze.pos) <= self.cfg.gaze_threshold_pos:
                scores.append(self.cfg.s_fixation_pos)

        # Using distance measurement tool
        if aircraft.active_dist_measurements:
            scores.append(self.cfg.s_dist_measurement)

        return max(scores)
    
    def compute_scores(self, current_time_ms: float, state: WorldState) -> None:
        if self.last_tick_time == 0.0:
            self.last_tick_time = current_time_ms
            return

        dt_s = (current_time_ms - self.last_tick_time) / 1000.0
        self.last_tick_time = current_time_ms
        
        is_mouse_idle = state.mouse.is_idle(current_time_ms)
        airspace = state.get_airspace(current_time_ms)

        scores = {}
        targets = {}

        for callsign, aircraft in airspace:
            targets[callsign] = self._calculate_target(aircraft, state, is_mouse_idle)
            scores[callsign] = self._apply_alpha_filter(self.scores.get(callsign, 0.0), targets[callsign], dt_s)

        self.targets = targets
        self.scores = scores