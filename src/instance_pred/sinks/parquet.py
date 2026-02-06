import time
import asyncio
import logging
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from .base import PredictionSink
from ..scoring import InstancePrediction
from ..utils import ThrottledLogger
from ..types import EndToken, _END

logger = logging.getLogger(__name__)

class ParquetSink(PredictionSink):
    _SCHEMA: Final[pa.Schema] = pa.schema([
        ("timestamp_ms", pa.float64()),
        ("callsign", pa.string()),
        ("score", pa.float64()),
        ("candidate_callsigns", pa.list_(pa.string())),
        ("candidate_scores", pa.list_(pa.float64())),
    ])

    def __init__(
        self,
        output_dir: Path,
        max_time_flush_sec: int | None,
        drop_when_full: bool,
        max_buffer_size: int,
        queue_size: int,
    ) -> None:
        self.max_buffer_size = max_buffer_size
        self.max_time_flush_sec = max_time_flush_sec
        self.drop_when_full = drop_when_full
        
        # Setup file
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = output_dir / f"task_instance_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.parquet"
        
        # Internal state
        self._queue: asyncio.Queue[InstancePrediction | EndToken] = asyncio.Queue(maxsize=queue_size)
        self._worker_task: asyncio.Task | None = None
        self._writer: pq.ParquetWriter | None = None

        # Logging and stats
        self._total_rows = 0
        self._total_preds_dropped = 0
        self._drop_logger = ThrottledLogger(logger, interval_sec=1)

        logger.info(f"ParquetSink ready. Writing to: {self.output_path}")
    
    async def send(self, pred: InstancePrediction) -> None:
        # Fail fast, zero latency added (drop data)
        # For running in production environment
        if self.drop_when_full:
            try:
                self._queue.put_nowait(pred)
            except asyncio.QueueFull:
                self._total_preds_dropped += 1
                self._drop_logger.warning("Queue is full, dropping prediction.")

        # If queue is full, this pauses the producer (backpressure)
        # For batch processing or data collection to ensure data integrity
        else:
            await self._queue.put(pred)
    
    async def _worker(self) -> None:
        """
        Final Optimized Worker.
        
        1. Waits for 1 item (Respecting flush_interval if buffer is dirty).
        2. Greedily drains remaining items up to `buffer_size`.
        3. Flushes.
        """
        buffer: list[InstancePrediction] = []
        last_flush_time = time.monotonic()
        
        # Localize for tight-loop speed
        queue = self._queue
        flush_interval = self.max_time_flush_sec
        max_buf = self.max_buffer_size

        while True:
            try:
                # Wait for first item indefinitely
                # BULK: Always wait
                # STREAMING: If buffer is empty
                if flush_interval is None or not buffer:
                    item = await queue.get()
                # Apply timeout in STREAMING if buffer is dirty
                else:
                    timeout = max(0.0, flush_interval - (time.monotonic() - last_flush_time))
                    item = await asyncio.wait_for(queue.get(), timeout=timeout)

                # Process first item
                if item is _END:
                    break
                buffer.append(item)

                # Greedy Drain
                # BULK: Grab all you can
                # STREAMING: Doesn't enter under normal operations, queue receives one by one (constant frequency)
                while not queue.empty() and len(buffer) < max_buf:
                    try:
                        if (item := queue.get_nowait()) is _END:
                            break
                        buffer.append(item)
                    except asyncio.QueueEmpty:
                        break

                # BULK: only flush on full
                # STREAMING: if buffer gets full before timeout
                if len(buffer) >= max_buf:
                    await self._flush(buffer)
                    buffer.clear()
                    last_flush_time = time.monotonic()

            except asyncio.TimeoutError:
                # STREAMING flush on timeout
                await self._flush(buffer)
                buffer.clear()
                last_flush_time = time.monotonic()
        
        # Final flush
        await self._flush(buffer)

    async def _flush(self, batch: list[InstancePrediction]) -> None:
        """Offloads the expensive conversion and IO to a thread."""
        if not batch:
            return
        
        try:
            self._total_rows += await asyncio.to_thread(self._write_sync, batch)
        except Exception as e:
            logger.error(f"Flush failed: {e}")
            self._total_preds_dropped += len(batch)

    def _write_sync(self, batch: list[InstancePrediction]) -> int:
        """
        Writes batch to Parquet.
        Uses list pre-allocation for maximum performance.
        """
        size = len(batch)
        # Pre-allocate columns (~15% speedup over appending)
        timestamps = [None] * size
        callsigns = [None] * size
        scores = [None] * size
        cand_calls = [[] for _ in range(size)]
        cand_scores = [[] for _ in range(size)]

        for i, pred in enumerate(batch):
            timestamps[i] = pred.timestamp_ms
            
            if (ac := pred.aircraft) is not None:
                callsigns[i] = ac.callsign
                scores[i] = ac.score
                cand_calls[i] = [c.callsign for c in pred.candidates]
                cand_scores[i] = [c.score for c in pred.candidates]

        table = pa.Table.from_arrays(
            [
                pa.array(timestamps, type=pa.float64()),
                pa.array(callsigns, type=pa.string()),
                pa.array(scores, type=pa.float64()),
                pa.array(cand_calls, type=pa.list_(pa.string())),
                pa.array(cand_scores, type=pa.list_(pa.float64())),
            ],
            schema=self._SCHEMA
        )
        
        if self._writer is None:
            self._writer = pq.ParquetWriter(
                self.output_path, 
                schema=self._SCHEMA, 
                compression="zstd",
                use_dictionary=True
            )
        
        self._writer.write_table(table)
        return size

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker())

    async def close(self) -> None:
        if self._worker_task:
            await self._queue.put(_END)
            await self._worker_task
            self._worker_task = None
        
        if self._writer:
            await asyncio.to_thread(self._writer.close)
            self._writer = None
            logger.info(f"Parquet closed. Written: {self._total_rows:,}, Dropped: {self._total_preds_dropped:,}")