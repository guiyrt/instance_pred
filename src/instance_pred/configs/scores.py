from pydantic import Field, BaseModel, PositiveFloat, PositiveInt
from typing import Annotated

from ..models import AttentionIndicator

Score = Annotated[float, Field(ge=0., le=100.)]

class TauSettings(BaseModel):
    rise: PositiveFloat = 0.2
    decay: PositiveFloat = 1.0

class GazeThresholdSettings(BaseModel):
    track_label: PositiveInt = 50
    track_pos: PositiveInt = 100

class ScoreSettings(BaseModel):
    # Settings
    tau: TauSettings = Field(default_factory=TauSettings)
    gaze_threshold: GazeThresholdSettings = Field(default_factory=GazeThresholdSettings)

    # Scores
    popup_opened: Score = 80.0
    label_selected: Score = 80.0
    label_hovered: Score = 60.0
    label_parked: Score = 15.0
    label_fixation: Score = 45.0
    aircraft_fixation: Score = 35.0
    dist_measurement: Score = 20.0

    def to_indicator_map(self) -> dict[AttentionIndicator, float]:
        """
        Compiles the human-readable Pydantic fields into an O(1) lookup dictionary
        for the hot loop to use when deriving the maximum score.
        """
        return {
            AttentionIndicator.POPUP_OPENED: self.popup_opened,
            AttentionIndicator.LABEL_SELECTED: self.label_selected,
            AttentionIndicator.LABEL_HOVERED: self.label_hovered,
            AttentionIndicator.LABEL_PARKED: self.label_parked,
            AttentionIndicator.LABEL_FIXATION: self.label_fixation,
            AttentionIndicator.AIRCRAFT_FIXATION: self.aircraft_fixation,
            AttentionIndicator.DIST_MEASUREMENT: self.dist_measurement,
        }