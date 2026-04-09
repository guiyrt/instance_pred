from pydantic import BaseModel

class NATSSinkConfig(BaseModel):
    enabled: bool = True
    subject: str = "intent.aircraft_attention_target"