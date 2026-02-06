import logging
from typing import Final

from ..models import TrackLabel, TrackPos

logger = logging.getLogger(__name__)


class AircraftState:
    __slots__ = (
        'callsign',
        'track_label',
        'track_pos',
        'active_dist_measurements',
    )

    TTL_MS: Final[int] = 10_000

    def __init__(
        self,
        callsign: str
    ) -> None:
        self.callsign: str = callsign
        self.track_label: TrackLabel | None = None
        self.track_pos: TrackPos | None = None

        self.active_dist_measurements: set[int] = set()

    def is_stale(self, current_time_ms: float) -> bool:
        return (self.track_label is None or self.track_label.is_stale(current_time_ms, self.TTL_MS)) and \
            (self.track_pos is None or self.track_pos.is_stale(current_time_ms, self.TTL_MS)) and \
            not self.active_dist_measurements
    
    def remove_dist_measurement(self, measurement_id: int) -> None:
        if measurement_id not in self.active_dist_measurements:
            logger.warning("Request to remove non-existing distance_measurement with id %d.", measurement_id)
        else:
            self.active_dist_measurements.remove(measurement_id)
    
    def add_dist_measurement(self, measurement_id: int) -> None:
        if measurement_id in self.active_dist_measurements:
            logger.warning("Request to add duplicate distance_measurement with id %d.", measurement_id)
        else:
            self.active_dist_measurements.add(measurement_id)