import math
from datetime import datetime

from .states import WorldState, AircraftState
from .models import InstancePrediction, ScoredAircraft, ScorerConfig, AttentionIndicator

class HeuristicScorer:
    """
    Stateful scoring engine.
    Maintains the current score and active indicators for every aircraft.
    """
    def __init__(self, config: ScorerConfig) -> None:
        self.cfg = config
        
        # { callsign: <value> }
        self.scores: dict[str, float] = {}
        self.active_indicators: dict[str, set[AttentionIndicator]] = {}
        
        # Track time to calculate internal dt
        self.last_update_time: datetime = datetime.fromtimestamp(0)
    
    def get_prediction(self) -> InstancePrediction:
        values: list[ScoredAircraft] = sorted(
            filter(
                lambda x: x.score > 1.0,
                (
                    ScoredAircraft(
                        callsign=callsign, 
                        score=score, 
                        indicators=self.active_indicators.get(callsign, set())
                    ) 
                    for callsign, score in self.scores.items()
                ),
            ),
            key=lambda x: x.score,
            reverse=True
        )

        return InstancePrediction(
            self.last_update_time,
            values[0] if values else None,
            values
        )
    
    def _apply_alpha_filter(self, current: float, target: float, dt_s: float) -> float:
        if dt_s <= 0:
            return current

        tau = self.cfg.tau_rise if target > current else self.cfg.tau_decay    
        alpha = 1.0 - math.exp(-dt_s / tau)
        
        return current + (target - current) * alpha

    def _evaluate_indicators(self, aircraft: AircraftState, state: WorldState, is_mouse_idle: bool) -> tuple[AttentionIndicator]:
        """
        Evaluates the world state and returns all currently active indicators for this aircraft.
        """
        indicators = list()

        # Pop-up
        if state.popup is not None and aircraft.callsign == state.popup.callsign:
            indicators.append(AttentionIndicator.POPUP_OPENED)

        # Label
        if aircraft.track_label is not None:
            if aircraft.track_label.is_selected:
                indicators.append(AttentionIndicator.LABEL_SELECTED)

            if aircraft.track_label.is_hovered:
                indicators.append(
                    AttentionIndicator.LABEL_PARKED
                    if is_mouse_idle 
                    else AttentionIndicator.LABEL_HOVERED
                )

        # Gaze
        if state.gaze.has_signal and state.gaze.is_fixating:
            if aircraft.track_label is not None and aircraft.track_label.contains(state.gaze.pos, self.cfg.gaze_threshold_label):
                indicators.append(AttentionIndicator.LABEL_FIXATION)

            if aircraft.track_pos is not None and aircraft.track_pos.pos.dist(state.gaze.pos) <= self.cfg.gaze_threshold_pos:
                indicators.append(AttentionIndicator.AIRCRAFT_FIXATION)

        # Distance Measurement
        if aircraft.active_dist_measurements:
            indicators.append(AttentionIndicator.DIST_MEASUREMENT)

        return tuple(indicators)
    
    def compute_scores(self, current_time: datetime, state: WorldState) -> None:
        if self.last_update_time is None:
            self.last_update_time = current_time
            return
                
        is_mouse_idle = state.mouse.is_idle(current_time)
        airspace = state.get_airspace(current_time)

        new_scores = {}
        new_indicators = {}

        for callsign, aircraft in airspace:
            # Determine active indicators
            indicators = self._evaluate_indicators(aircraft, state, is_mouse_idle)
            
            # Derive target score dynamically based on active indicators
            target_score = max(
                (self.cfg.indicator_scores[ind] for ind in indicators), 
                default=0.0
            )
            
            # Apply low-pass filter
            new_scores[callsign] = self._apply_alpha_filter(
                self.scores.get(callsign, 0.0),
                target_score,
                (current_time - self.last_update_time).total_seconds()
            )
            new_indicators[callsign] = indicators

        # Update state
        self.scores = new_scores
        self.active_indicators = new_indicators
        self.last_update_time = current_time
