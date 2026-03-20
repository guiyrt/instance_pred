from pydantic import BaseModel, PositiveInt

class TerminalSinkConfig(BaseModel):
    enabled: bool = True
    refresh_per_sec: PositiveInt = 10