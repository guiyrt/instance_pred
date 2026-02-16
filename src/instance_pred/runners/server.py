import asyncio
import struct
import time
import zmq.asyncio
from typing import Sequence, Final
import google.protobuf.json_format

from aware_protos.aware.proto import messages_pb2
import nats
import zlib

from .base import PredictionRunner
from ..task_instance_prediction import IntentSystem
from ..sinks import PredictionSink

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
        asd_nats_host: str,
        sampling_interval_ms: int,
    ):
        super().__init__(system, sinks, sampling_interval_ms)
        self.gaze_zmq_host = gaze_zmq_host
        self.asd_nats_host = asd_nats_host
        self._running = False

    async def run(self):
        """The main entry point for the application."""
        self.logger.info("Starting Intent Engine...")
        self._running = True
        
        await self.start_sinks()

        # Create the tasks for our 3 concurrent loops
        tasks = (
            asyncio.create_task(self._gaze_loop(), name="Gaze_ZMQ"),
            asyncio.create_task(self._asd_loop(), name="ASD_NATS"),
            asyncio.create_task(self._predict_loop(), name="Predictor")
        )

        try:
            # Run all loops until one fails or are cancelled
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.logger.info("Shutdown signal received.")
        except Exception as e:
            self.logger.critical(f"Unexpected system crash: {e}", exc_info=True)
        finally:
            self._running = False
            for t in tasks:
                t.cancel()
            
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.close_sinks()
            self.logger.info("Shutdown complete.")
    
    def _parse_proto(self, payload: str) -> messages_pb2.Event:
        return google.protobuf.json_format.Parse(payload, messages_pb2.Event())

    async def _asd_loop(self):
        self.logger.info(f"Connecting to NATS: {self.asd_nats_host}")
        nc = nats.NATS()

        while self._running:
            try:
                await asyncio.wait_for(
                    nc.connect(
                        self.asd_nats_host,
                        allow_reconnect=True,
                        max_reconnect_attempts=-1
                    ),
                    timeout=5
                )
                self.logger.info("Successfully connected to NATS.")
                break # Exit while loop on success
                
            except (asyncio.TimeoutError, Exception) as e:
                self.logger.warning(f"NATS connection failed. Retrying in 5s... ({type(e).__name__})")
        
        try:
            sub = await nc.subscribe("polaris.ASDEvent")

            async for msg in sub.messages:
                data = msg.data

                if msg.header and msg.header["deflate"] == "1":
                    data = zlib.decompress(data)
                
                event = await asyncio.to_thread(self._parse_proto, data.decode())
                self.system.ingest_proto_event(event)
        
        except asyncio.CancelledError:
            pass # Standard shutdown
        except Exception as e:
            self.logger.error(f"ASD NATS Loop crashed: {e}", exc_info=True)
        finally:
            await sub.unsubscribe()
            await nc.close()

    async def _gaze_loop(self):
        """High-Frequency Gaze Input Loop (Consumer)."""
        ctx = zmq.asyncio.Context()
        sock = ctx.socket(zmq.SUB)
        gaze_struct = struct.Struct("!qii?")
        
        # Auto-reconnect if ZMQ publisher dies/restarts
        sock.setsockopt(zmq.RECONNECT_IVL, 1000)
        sock.connect(self.gaze_zmq_host)
        sock.subscribe(b"gaze")
        
        self.logger.info(f"Connected to Gaze ZMQ stream: {self.gaze_zmq_host}")
        
        try:
            while self._running:
                msg = await sock.recv()
                self.system.ingest_gaze(*gaze_struct.unpack(msg[4:]))

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