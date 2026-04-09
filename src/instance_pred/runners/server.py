from datetime import datetime, timezone
import asyncio
import time
from typing import Sequence, Final
import google.protobuf.json_format

from aware_protos.aware.proto import messages_pb2
from aware_protos.zhaw.protobuf import gaze_pb2

import nats
import zlib

from .base import PredictionRunner
from ..task_instance_prediction import IntentSystem
from ..sinks import PredictionSink


class ServerRunner(PredictionRunner):
    """
    Orchestrates the Real-time prediction engine.
    """

    _LAG_WARNING_MS: Final[int] = 50
    _LAG_RESET_MS: Final[int] = 500
    
    def __init__(
        self,
        system: IntentSystem,
        sinks: Sequence[PredictionSink],
        nc: nats.NATS,
        sampling_interval_ms: int,
    ):
        super().__init__(system, sinks, sampling_interval_ms)
        self.nc = nc
        
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self):
        """The main entry point for the application."""
        self.logger.info("Starting Intent Engine...")
        self._running = True
        
        await self.start_sinks()

        # Create the tasks for our 3 concurrent loops
        self._tasks = [
            asyncio.create_task(self._gaze_loop(), name="Gaze_NATS"),
            asyncio.create_task(self._asd_loop(), name="ASD_NATS"),
            asyncio.create_task(self._predict_loop(), name="Predictor")
        ]

    async def stop(self) -> None:
        self._running = False

        for t in self._tasks:
            t.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.close_sinks()
        self.logger.info("Shutdown complete.")
    
    def _parse_proto(self, payload: str) -> messages_pb2.Event:
        return google.protobuf.json_format.Parse(
            payload,
            messages_pb2.Event(),
            ignore_unknown_fields=True
        )

    async def _asd_loop(self) -> None:
        """Consumes JSON-encoded ASD Events."""
        try:
            # Subscribe using the shared client
            sub = await self.nc.subscribe("polaris.ASDEvent")

            async for msg in sub.messages:
                try:
                    data = msg.data

                    if msg.header and msg.header.get("deflate") == "1":
                        data = zlib.decompress(data)
                    
                    event = await asyncio.to_thread(self._parse_proto, data.decode())
                    self.system.ingest_proto_event(event)
                
                except Exception as e:
                    self.logger.error("Failed to process single ASD message: %s", e)
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"ASD NATS loop failed: {e}", exc_info=True)

    async def _gaze_loop(self):
        """Consumes High-Frequency Binary Gaze Events."""
        try:
            # Subscribe using the shared client
            sub = await self.nc.subscribe("gaze")
            gaze_event = gaze_pb2.GazeScreenPosition()

            async for msg in sub.messages:
                gaze_event.ParseFromString(msg.data)
                
                self.system.ingest_gaze(
                    gaze_event.timestamp, 
                    gaze_event.x, 
                    gaze_event.y, 
                    gaze_event.is_valid
                )
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Gaze NATS Loop crashed: {e}", exc_info=True)

    async def _predict_loop(self):
        """Predicts, broadcasts, and sleeps."""
        interval_sec = self.sampling_interval_ms / 1000.0        
        next_tick = time.monotonic()
        
        try:
            while self._running:
                pred = self.system.get_prediction(datetime.now(timezone.utc))
                await self.broadcast(pred)
                
                next_tick += interval_sec
                sleep_duration = next_tick - time.monotonic()
                
                if sleep_duration > 0:
                    await asyncio.sleep(sleep_duration)
                else:
                    lag_ms = abs(sleep_duration) * 1000

                    if lag_ms > self._LAG_RESET_MS:
                        next_tick = time.monotonic()
                        self.logger.warning(f"System clock reset, was {lag_ms:.1f}ms behind schedule")
                    
                    elif lag_ms > self._LAG_WARNING_MS:
                        self.logger.warning(f"System lagging {lag_ms:.1f}ms behind schedule")

        except asyncio.CancelledError:
            pass