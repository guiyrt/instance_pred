import logging
from typing import ItemsView

from ..models import Popup, TrackLabel, TrackPos
from .aircraft import AircraftState
from .gaze import GazeState
from .mouse import MouseState

logger = logging.getLogger(__name__)


class WorldState:
    """
    clearance|transfer are ignored because it's considered the answer.
    route_interaction|keyboard_shortcut|track_mark|speed_vector have little to no meaningful data.
    sep_tool might be useful, but events show weird data.
    """
    __slots__ = ("_airspace", "gaze", "mouse", "_dist_measurement_index", "popup")
    
    def __init__(self):
        self._airspace: dict[str, AircraftState] = {}
        self.gaze: GazeState = GazeState()
        self.mouse: MouseState = MouseState()

        self._dist_measurement_index: dict[int, tuple[str,...]] = {}
        """Key is distance_measurement id, values are aircraft monitored (1 or 2)"""
        self.popup: Popup | None = None

    def _prune(self, current_time_ms: int) -> None:
        for callsign in list(self._airspace):
            if self._airspace[callsign].is_stale(current_time_ms):
                del self._airspace[callsign]

    def _get_aircraft(self, callsign: str) -> AircraftState:
        if callsign not in self._airspace:
            self._airspace[callsign] = AircraftState(callsign)
        
        return self._airspace[callsign]
    
    def get_airspace(self, current_time_ms: int) -> ItemsView[str, AircraftState]:        
        self._prune(current_time_ms)
        return self._airspace.items()
    
    def update_track_label(self, callsign: str, track_label: TrackLabel) -> None:
        self._get_aircraft(callsign).track_label = track_label

    def update_track_pos(self, callsign: str, track_pos: TrackPos) -> None:
        self._get_aircraft(callsign).track_pos = track_pos

    def _set_popup(self, popup: Popup) -> None:
        if self.popup is not None:
            logging.warning("Overwriting %s with %s", self.popup, popup)

        self.popup = popup
    
    def _clear_popup(self, popup: Popup) -> None:
        if self.popup.callsign is None:
            logging.warning("Received stale close for %s", popup)
        elif self.popup.callsign == popup.callsign:
            self.popup = None
        else:
            logging.warning("Ignoring close of %s, current is %s", popup, self.popup)
    
    def update_popup(self, popup: Popup, opened: bool) -> None:
        self._set_popup(popup) if opened else self._clear_popup(popup)

    def add_dist_measurement(self, measurement_id: int, first_callsign: str | None, second_callsign: str | None) -> None:
        callsigns = tuple(filter(lambda x: isinstance(x, str), [first_callsign, second_callsign]))

        # Register even with no callsigns, so remove works correctly
        self._dist_measurement_index[measurement_id] = callsigns

        # Register in AircraftStates
        for callsign in callsigns:
            self._get_aircraft(callsign).add_dist_measurement(measurement_id)

    def remove_dist_measurement(self, measurement_id: int) -> None:
        if measurement_id in self._dist_measurement_index:
            for callsign in self._dist_measurement_index.pop(measurement_id):
                self._get_aircraft(callsign).remove_dist_measurement(measurement_id)
        else:
            logger.warning("Received remove for non-existing measurement_id %d", measurement_id)
                    
    def process_gaze_event(self, x: float | None, y: float | None, timestamp_ms: float) -> None:
        self.gaze.update(x, y, timestamp_ms)