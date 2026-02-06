import asyncio
from functools import cached_property
import time
from typing import Sequence, Final

from .base import PredictionRunner
from ..session_loader import SessionLoader
from ..task_instance_prediction import IntentSystem
from ..sinks import PredictionSink


class OfflineRunner(PredictionRunner):
    _FINAL_DECAY_TIMEOUT_MS: Final[float] = 5 * 1_000
    """Safeguard timeout to exit final decay loop."""

    def __init__(
        self,
        session: SessionLoader,
        system: IntentSystem,
        sinks: Sequence[PredictionSink],
        playback_speed: float | None,
        sampling_interval_ms: int,
    ):
        super().__init__(system, sinks, sampling_interval_ms)
        self.session = session
        self.playback_speed = playback_speed

    @cached_property
    def in_realtime(self) -> bool:
        return self.playback_speed is not None

    async def run(self) -> None:
        """Executes the timeline."""
        try:

            if len(self.session) == 0:
                self.logger.info("Empty session.")
                return

            await self.start_sinks()

            # Setup of event stream
            stream = self.session.stream()
            _END_OF_STREAM = object()
            event = next(stream, _END_OF_STREAM)

            # Setup for real-time execution
            start_wall_time = time.monotonic()

            async def wait_until(target_time: float) -> None:
                elapsed_sim_time = (target_time - self.session.start_timestamp) / 1000.0
                target_wall_time = start_wall_time + (elapsed_sim_time / self.playback_speed)
                
                # Sleep until target_wall time
                if (delay := target_wall_time - time.monotonic()) > 0:
                    await asyncio.sleep(delay)

            for pred_time in range(self.session.start_timestamp, self.session.end_timestamp + 1, self.sampling_interval_ms):
                # Process events until `pred_time`
                while event is not _END_OF_STREAM and event.timestamp_ms <= pred_time:
                    self.system.ingest_row_event(event)
                    event = next(stream, _END_OF_STREAM)
                
                if self.in_realtime:
                    await wait_until(pred_time)
                
                # Broadcasting prediction to sinks
                await self.broadcast(self.system.get_prediction(pred_time))

            # <<< Final score decay >>>
            self.logger.info("Events processing finished, decaying scores to 0.")
            timeout = self.session.end_timestamp + self._FINAL_DECAY_TIMEOUT_MS
            pred_time = self.session.end_timestamp + self.sampling_interval_ms
            
            while self.system.has_active_scores() and pred_time < timeout:
                if self.in_realtime:
                    await wait_until(pred_time)

                await self.broadcast(self.system.get_prediction(pred_time))
                pred_time += self.sampling_interval_ms

        finally:
            # This ensures even if the loop crashes, your Parquet file is saved
            await self.close_sinks()