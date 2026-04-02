import logging
import nats

from .base import PredictionSink
from ..scoring import InstancePrediction

from aware_protos.zhaw.protobuf.aircraft_attention_target_pb2 import AircraftAttentionTarget

logger = logging.getLogger(__name__)

class NATSSink(PredictionSink):
    """
    Publishes the highest-scoring aircraft to NATS using Protobuf.
    Designed for real-time sub-millisecond latency.
    """
    def __init__(
        self,
        nats_host: str,
        subject: str = "intent.aircraft_attention_target",
        nc: nats.NATS | None = None
    ):
        self.nats_host = nats_host
        self.nc = nc
        self.subject = subject
        self._owns_nc = (nc is None)
        
        # Pre-instantiate Protobuf object for memory reuse
        self._proto = AircraftAttentionTarget()
    
    async def start(self) -> None:
        """Connect to NATS if we own the connection."""
        if self._owns_nc:
            self.nc = nats.NATS()
            logger.info(f"NATSSink initializing standalone connection to {self.nats_host}...")

            await self.nc.connect(
                self.nats_host,
                allow_reconnect=True,
                max_reconnect_attempts=-1
            )

            logger.info("NATSSink standalone connection established.")
        elif self.nc.is_connected:
            logger.info("NATSSink shared connection ready.")
        else:
            logger.warning("NATSSink received a non-connected NATS client!")

    async def send(self, pred: InstancePrediction) -> None:
        """Serializes and publishes the top prediction."""
        try:
            p = self._proto
            p.Clear()

            p.timestamp.FromDatetime(pred.timestamp)
            
            if pred.candidates: 
                # Assuming candidates are already sorted by score descending in the predictor
                p.primary_target_callsign = pred.primary_target.callsign
                
                # Populate the repeated nested messages
                for c in pred.candidates:
                    target_msg = p.targets.add()
                    target_msg.callsign = c.callsign
                    target_msg.score = c.score
                    # Keep values (integers) for NATS efficiency
                    target_msg.active_indicators.extend([ind.value for ind in c.indicators])
            
            # Serialize to Binary Protobuf and Publish
            await self.nc.publish(self.subject, p.SerializeToString())
            
        except Exception as e:
            logger.error(f"Failed to publish prediction to NATS: {e}")

    async def close(self) -> None:
        """Gracefully drain the connection ONLY if we created it."""
        if self._owns_nc and self.nc and self.nc.is_connected:
            logger.info("Draining standalone NATS connection in NATSSink...")
            await self.nc.drain()