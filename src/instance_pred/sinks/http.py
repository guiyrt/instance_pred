import aiohttp

from .base import PredictionSink
from ..task_instance_prediction import InstancePrediction

# TODO: Not ready for consumption.
class HttpSink(PredictionSink):
    def __init__(self, url: str):
        self.url = url
        self.session = None

    async def _ensure_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def send(self, pred: InstancePrediction) -> None:
        await self._ensure_session()
        
        payload = {
            "timestamp": pred.timestamp_ms,
            "callsign": pred.aircraft.callsign,
            "score": round(pred.aircraft.score, 2)
        }
        
        try:
            await self.session.post(self.url, json=payload)
        except Exception as e:
            print(f"HTTP Sink Error: {e}")