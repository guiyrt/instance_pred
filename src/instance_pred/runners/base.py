import asyncio
import logging
from abc import ABC
from typing import Sequence

from ..task_instance_prediction import IntentSystem, InstancePrediction
from ..sinks import PredictionSink

class PredictionRunner(ABC):
    """
    Abstract Orchestrator.
    Responsibility: 
    1. Manages Lifecycle of Resources (System & Sinks).
    2. Defines the Broadcast interface.
    3. Enforces the contract for execution (Run loop).
    """
    def __init__(
        self, 
        system: IntentSystem,
        sinks: Sequence[PredictionSink],
        sampling_interval_ms: int,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.system = system
        self.sinks = sinks
        self.sampling_interval_ms = sampling_interval_ms

    async def broadcast(self, pred: InstancePrediction) -> None:
        """
        Broadcasts prediction to all sinks concurrently.
        Swallows exceptions from individual sinks to keep the engine running.
        """
        if not self.sinks:
            return

        results = await asyncio.gather(
            *(sink.send(pred) for sink in self.sinks), 
            return_exceptions=True
        )

        for sink, result in zip(self.sinks, results):
            if isinstance(result, Exception):
                self.logger.error(f"Sink {type(sink).__name__} failed: {result}")

    async def start_sinks(self) -> None:
        """
        Initialize all resources. 
        Raises exception immediately if any sink fails to start (Fail Fast).
        """
        self.logger.info("Starting sinks...")
        await asyncio.gather(*(sink.start() for sink in self.sinks))
    
    async def close_sinks(self) -> None:
        """
        Gracefully close all sinks.
        Attempts to close ALL sinks even if one fails.
        """
        self.logger.info("Closing sinks...")
        # return_exceptions=True ensures we attempt to close B even if A fails.
        results = await asyncio.gather(
            *(sink.close() for sink in self.sinks), 
            return_exceptions=True
        )
        
        for result in results:
            if isinstance(result, Exception):
                self.logger.warning(f"Error during sink shutdown: {result}")