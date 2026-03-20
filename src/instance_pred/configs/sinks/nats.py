from pydantic import BaseModel

class NATSSinkConfig(BaseModel):
    enabled: bool = True
    host: str = "nats://localhost:4222"