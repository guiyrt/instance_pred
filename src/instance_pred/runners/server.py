import asyncio
import struct
import time
import zmq.asyncio
from contextlib import asynccontextmanager
from typing import Sequence, Final

from fastapi import FastAPI, Request, Response
from aware_protos.aware.proto import messages_pb2

from .base import PredictionRunner
from ..task_instance_prediction import IntentSystem
from ..sinks import PredictionSink

# Pre-compiled struct for ZMQ unpacking (!=Network Endian, d=double/float64)
# Format: x (double), y (double), timestamp (double)
_GAZE_STRUCT = struct.Struct("!ddd")

class ServerRunner(PredictionRunner):
    """
    Orchestrates the Real-time prediction engine.
    
    Responsibilities:
    1. Hosts the FastAPI server for Event ingestion.
    2. Subscribes to ZMQ for high-frequency Gaze data.
    3. Ticks the logic clock (sampling_interval) to generate predictions.
    """

    _LAG_WARNING_MS: Final[int] = 50
    _LAG_RESET_MS: Final[int] = 2_000
    
    def __init__(
        self,
        system: IntentSystem,
        sinks: Sequence[PredictionSink],
        gaze_zmq_host: str,
        sampling_interval_ms: int,
    ):
        super().__init__(system, sinks, sampling_interval_ms)
        self.gaze_zmq_host = gaze_zmq_host
        
        # Internal State
        self._running = False
        self._zmq_task: asyncio.Task | None = None
        self._predict_task: asyncio.Task | None = None

        # Expose the app so uvicorn can serve it
        self.app = FastAPI(title="Intent Engine", lifespan=self._lifespan)
        self.app.post("/asd")(self._handle_asd_post)
        self.app.get("/health")(self._health_check)

    @asynccontextmanager
    async def _lifespan(self, _: FastAPI):
        """
        Manages the startup/shutdown sequence.
        Crucial for ensuring Sinks are ready before we accept data.
        """
        self.logger.info("System Starting...")
        self._running = True
        
        # Start
        await self.start_sinks()
        self._zmq_task = asyncio.create_task(self._zmq_loop())
        self._predict_task = asyncio.create_task(self._predict_loop())
        
        yield # Server is running and accepting requests
        
        self.logger.info("System shutting down...")
        self._running = False
        
        # Stop
        self._zmq_task.cancel()
        self._predict_task.cancel()
        await asyncio.gather(self._zmq_task, self._predict_task, return_exceptions=True)
        await self.close_sinks()

        self.logger.info("Shutdown complete.")

    async def _health_check(self):
        return {
            "status": "ok" if self._running else "starting",
            "sinks": [type(s).__name__ for s in self.sinks],
            "zmq_connected": self.gaze_zmq_host
        }
    
    async def _parse_proto(self, payload: bytes) -> messages_pb2.Event:
        event = messages_pb2.Event()
        event.ParseFromString(payload)
        return event

    async def _handle_asd_post(self, request: Request):
        """Ingest Protobuf Events via HTTP."""
        try:
            payload = await request.body()
            event = await asyncio.to_thread(self._parse_proto, payload)
            self.system.ingest_proto_event(event)
            
            return Response(status_code=202)
            
        except Exception as e:
            self.logger.warning(f"Failed to process ASD event: {e}")
            return Response(content="Invalid Protobuf", status_code=400)

    async def _zmq_loop(self):
        """High-Frequency Gaze Input Loop (Consumer)."""
        ctx = zmq.asyncio.Context()
        sock = ctx.socket(zmq.SUB)
        
        # Auto-reconnect if ZMQ publisher dies/restarts
        sock.setsockopt(zmq.RECONNECT_IVL, 1000)
        sock.connect(self.gaze_zmq_host)
        sock.subscribe(b"gaze")
        
        self.logger.info(f"Connected to Gaze ZMQ stream: {self.gaze_zmq_host}")
        
        try:
            while self._running:
                msg = await sock.recv()
                
                # Fast validation & slicing
                if len(msg) == 28: # 4 bytes 'gaze' + 3 doubles (8 bytes each)
                    self.system.ingest_gaze(*_GAZE_STRUCT.unpack(msg[4:]))
                    
        except asyncio.CancelledError:
            pass # Standard shutdown
        except Exception as e:
            self.logger.error(f"Gaze ZMQ Loop crashed: {e}", exc_info=True)
        finally:
            sock.close()
            ctx.term()

    async def _predict_loop(self):
        """Predicts, broadcasts, and sleeps."""
        interval_sec = self.sampling_interval_ms / 1000.0        
        next_tick = time.monotonic()
        
        try:
            while self._running:
                # Get prediction and broadcast
                pred = self.system.get_prediction(time.time() * 1000.0)
                await self.broadcast(pred)
                
                # Calculate next interval
                next_tick += interval_sec
                sleep_duration = next_tick - time.monotonic()
                
                if sleep_duration > 0:
                    await asyncio.sleep(sleep_duration)
                else:
                    # Lag Detection
                    lag_ms = abs(sleep_duration) * 1000

                    if lag_ms > self._LAG_WARNING_MS:
                        self.logger.warning(f"System lagging {lag_ms:.1f}ms behind schedule")
                    elif lag_ms > self._LAG_RESET_MS:
                        next_tick = time.monotonic()
                        self.logger.warning(f"System clock reset, was {lag_ms:.1f}ms behind schedule")

        except asyncio.CancelledError:
            pass