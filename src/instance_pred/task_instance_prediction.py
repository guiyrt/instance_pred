from math import isnan
from datetime import datetime, timedelta
from datetime import timezone

from aware_protos.tern.asd.events import asd_events_pb2
from aware_protos.aware.proto import messages_pb2

from .states import WorldState
from .models import TrackLabel, TrackPos, Popup
from .scoring import HeuristicScorer, ScorerConfig, InstancePrediction
from .session_loader import EventType, RowEvent

class IntentSystem:
    def __init__(self, config: ScorerConfig):
        self.world = WorldState()
        self.scorer = HeuristicScorer(config)

    def has_active_scores(self) -> bool:
        """Returns True if any aircraft has a score above 1."""
        if not self.scorer.scores:
            return False
        
        return any(score > 1.0 for score in self.scorer.scores.values())

    def ingest_proto_event(self, event: messages_pb2.Event) -> None:
        if not event.WhichOneof("payload") == "asd_event":
            return

        payload: asd_events_pb2.Event = event.asd_event
        timestamp: datetime = event.timestamp.ToDatetime(timezone.utc)

        match payload.WhichOneof("event"):
            case "mouse_position":
                self.world.mouse.update(payload.mouse_position.x, payload.mouse_position.y, timestamp)
            
            case "track_label_position":
                self.world.update_track_label(
                    payload.track_label_position.flight_id.callsign,
                    TrackLabel.from_proto(payload.track_label_position, timestamp)
                )
            
            case "track_screen_position":
                self.world.update_track_pos(
                    payload.track_screen_position.flight_id.callsign,
                    TrackPos.from_proto(payload.track_screen_position, timestamp)
                )
            
            case "popup":
                self.world.update_popup(
                    Popup.from_proto(payload.popup, timestamp),
                    payload.popup.opened
                )

            case "distance_measurement":
                if payload.distance_measurement.HasField("added"):
                    self.world.add_dist_measurement(
                        payload.distance_measurement.added.measurement_id,
                        payload.distance_measurement.added.first.flight_id.callsign,
                        payload.distance_measurement.added.second.flight_id.callsign,
                    )

                elif payload.distance_measurement.HasField("removed"):
                    self.world.remove_dist_measurement(payload.distance_measurement.removed.measurement_id)

    def ingest_row_event(self, row: RowEvent) -> None:
        match row.type:
            case EventType.MOUSE_POSITION:
                self.world.mouse.update(row.data.x, row.data.y, row.data.timestamp_ms.to_pydatetime())
            
            case EventType.TRACK_LABEL_POSITION:
                self.world.update_track_label(row.data.callsign, TrackLabel.from_row(row.data))
            
            case EventType.TRACK_SCREEN_POSITION:
                self.world.update_track_pos(row.data.callsign, TrackPos.from_row(row.data))
            
            case EventType.POPUP:
                self.world.update_popup(Popup.from_row(row.data), row.data.opened)

            case EventType.DISTANCE_MEASUREMENT:
                if not isnan(row.data.added__measurement_id):
                    self.world.add_dist_measurement(
                        int(row.data.added__measurement_id),
                        row.data.added__first__callsign,
                        row.data.added__second__callsign,
                    )
                    
                if not isnan(row.data.removed__measurement_id):
                    self.world.remove_dist_measurement(
                        int(row.data.removed__measurement_id)
                    )

            case EventType.GAZE:
                self.ingest_gaze(
                    row.data.timestamp_ms.to_pydatetime(),
                    int(row.data.gaze_x_px) if not isnan(row.data.gaze_x_px) else -1,
                    int(row.data.gaze_y_px) if not isnan(row.data.gaze_y_px) else -1,
                    not isnan(row.data.gaze_x_px) and not isnan(row.data.gaze_y_px)
                )

    def ingest_gaze(self, timestamp: datetime, x: int , y: int, valid: bool) -> None:
        """
        The 'Heartbeat'. Updates Physics and Scoring.
        """
        self.world.process_gaze_event(timestamp, x if valid else None, y if valid else None)
        self.scorer.compute_scores(timestamp, self.world)
        
    def get_prediction(self, timestamp: datetime) -> InstancePrediction:
        # Recompute if more than 10ms elapsed (suggests gaze loss of signal)
        if (timestamp - self.scorer.last_update_time) > timedelta(milliseconds=10):
            self.scorer.compute_scores(timestamp, self.world)

        return self.scorer.get_prediction()