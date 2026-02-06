from abc import ABC, abstractmethod

from ..scoring import InstancePrediction

class PredictionSink(ABC):
    @abstractmethod
    async def send(self, pred: InstancePrediction) -> None:
        pass

    async def start(self) -> None:
        """Start the sink"""
        pass

    async def close(self) -> None:
        """Gracefully shut down the sink"""
        pass

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_):
        await self.close()