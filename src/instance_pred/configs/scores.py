from pydantic import Field, BaseModel, PositiveFloat, PositiveInt
from typing import Annotated

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
    pos_fixation: Score = 35.0
    dist_measurement: Score = 20.0