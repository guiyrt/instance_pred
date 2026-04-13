import asyncio
import logging
import json
from pathlib import Path
import nats

from .runners.server import ServerRunner
from .factories import create_sinks, create_scorer_config
from .configs import OrchestratedSettings
from .task_instance_prediction import IntentSystem


logger = logging.getLogger(__name__)

class PredictionManager:
    def __init__(self, settings: OrchestratedSettings, nc: nats.NATS):
        self.settings = settings

        self.data_dir: Path = settings.data_dir
        self.health_subject: str = settings.health_subject
        self.cmds_subject: str = settings.cmds_subject

        self.nc = nc
        self.runner: ServerRunner | None = None
        self._heartbeat_task: asyncio.Task | None = None

    @property
    def is_recording(self) -> bool:
        return self.runner is not None
    
    async def start(self, sub_dir: str | None = None) -> None:
        """Creates and starts a fresh runner with new sinks."""
        if self.runner:
            raise RuntimeError("Engine is already running a session.")
        
        session_path = (
            self.data_dir / sub_dir / "intent"
            if sub_dir is not None
            else self.data_dir
        )
        session_path.mkdir(parents=True, exist_ok=True)

        self.runner = ServerRunner(
            system=IntentSystem(create_scorer_config(self.settings)),
            sinks=create_sinks(self.settings, nc=self.nc, output_dir=session_path),
            nc=self.nc,
            sampling_interval_ms=self.settings.sampling_interval_ms
        )

        logger.info(f"Starting Prediction Engine. Output dir: {session_path}")
        await self.runner.start()

    async def stop(self) -> None:
        """Cleans up the runner."""
        if self.runner:
            await self.runner.stop()
            self.runner = None
            logger.info("Prediction Engine stopped.")

    async def listen_to_nats(self, stop_event: asyncio.Event):
        """Orchestration loop: Heartbeats + Commands."""
        
        async def heartbeat():
            try:
                while not stop_event.is_set():
                    if self.nc.is_connected:
                        await self.nc.publish(
                            self.settings.health_subject,
                            json.dumps({"is_recording": self.is_recording}).encode()
                        )
                    
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Heartbeat task crashed: {e}")

        async def cmd_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                cmd = data.get("cmd")
                
                if cmd == "start":
                    await self.start(data.get("session_id", None))
                    await msg.respond(json.dumps({"status": "ok"}).encode())
                
                elif cmd == "stop":
                    await self.stop()
                    await msg.respond(json.dumps({"status": "ok"}).encode())
                
                else:
                    await msg.respond(json.dumps({"status": "error", "error": f"Unknown cmd: {cmd}"}).encode())
            
            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                await msg.respond(json.dumps({"status": "error", "error": str(e)}).encode())

        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(heartbeat())
        
        # Subscribe to Commands
        sub = await self.nc.subscribe(self.cmds_subject, cb=cmd_handler)
        logger.info("STANDBY: listening for NATS commands...")
        
        try:
            # Block until the main app signals shutdown
            await stop_event.wait()
        finally:
            logger.info("Tearing down Orchestrator listener...")
            await sub.unsubscribe()
            
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
            
            await self.stop() # Ensure runner stops if container is killed mid-recording