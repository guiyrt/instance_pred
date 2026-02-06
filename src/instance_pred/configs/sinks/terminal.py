from pydantic import BaseModel, PositiveInt

class TerminalSinkConfig(BaseModel):
    enabled: bool = True
    top_n: PositiveInt = 5
    refresh_per_sec: PositiveInt = 10