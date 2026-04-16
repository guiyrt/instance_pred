import asyncio
import typer
from pathlib import Path
from typing import Annotated, Optional
import logging
import nats
from nats.errors import NoServersError
import signal

from .configs import ServerSettings, BulkSettings, OrchestratedSettings, LoggingConfig
from .session_loader import SessionLoader
from .task_instance_prediction import IntentSystem
from .runners import ServerRunner, OfflineRunner
from .factories import create_scorer_config, create_sinks
from .manager import PredictionManager

def setup_signals(stop_event: asyncio.Event):
    """Binds Docker shutdown signals (SIGTERM/SIGINT) to our async stop_event."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

async def setup_nats(host: str) -> nats.NATS:
    """
    Initializes NATS with custom logging to prevent traceback spam.
    """
    nc = nats.NATS()

    async def disconnected_cb():
        logger.warning("NATS: Connection disconnected.")

    async def reconnected_cb():
        logger.info(f"NATS: Connection restored to {nc.connected_url.netloc}")

    async def error_cb(e):
        # Ignore common network noise during background reconnect attempts
        if isinstance(e, (asyncio.TimeoutError, ConnectionRefusedError, OSError)):
            return

        err_msg = str(e).strip()

        # Some NATS specific EOF/disconnect errors might bypass the instance check
        if "empty response from server" in err_msg or "UnexpectedEOF" in err_msg:
            return

        # If it's an error with an empty string, log its class name instead
        if not err_msg:
            err_msg = type(e).__name__
            
        logger.error(f"NATS Internal Error: {err_msg}")

    async def closed_cb():
        logger.info("NATS: Connection closed.")

    # Connection Loop
    while True:
        try:
            await nc.connect(
                host,
                allow_reconnect=True,
                max_reconnect_attempts=-1, # Infinite reconnection
                reconnect_time_wait=2, # Wait 2s between attempts
                disconnected_cb=disconnected_cb,
                reconnected_cb=reconnected_cb,
                error_cb=error_cb,
                closed_cb=closed_cb,
            )
            logger.info(f"NATS: Initial connection established to {host}")
            return nc
        except (asyncio.TimeoutError, NoServersError, OSError) as e:
            logger.warning(f"NATS: Waiting for server at {host}... ({e})")
            await asyncio.sleep(5)

def setup_logger(settings: LoggingConfig):
    logging.getLogger("nats").setLevel(logging.ERROR)
    logging.getLogger("nats.aio.client").setLevel(logging.CRITICAL)
    logging.basicConfig(level=settings.level, format=settings.format)

app = typer.Typer(no_args_is_help=True, add_completion=False)

logger = logging.getLogger(__name__)

@app.command()
def serve():
    """Start the Real-time Prediction Server (Standalone)."""
    settings = ServerSettings()
    setup_logger(settings.logging)
    logger.debug(settings)

    async def _run():
        stop_event = asyncio.Event()
        setup_signals(stop_event)

        nc = await setup_nats(settings.nats_host)
        
        runner = ServerRunner(
            system=IntentSystem(create_scorer_config(settings)),
            sinks=create_sinks(settings, nc=nc),
            nc=nc,
            sampling_interval_ms=settings.sampling_interval_ms
        )

        await runner.start()
        
        try:
            logger.info("Standalone Server is running. Press Ctrl+C or stop container to exit.")
            await stop_event.wait()
        finally:
            logger.info("Shutting down ServerRunner...")
            await runner.stop()
            await nc.drain()

    try:
        asyncio.run(_run())
        logger.info("Shutdown complete.")
    except Exception as e:
        logger.critical(f"System failure: {e}", exc_info=True)
        raise typer.Exit(1)


@app.command()
def launch():
    """Orchestrated mode (Waits for Command Center)."""
    settings = OrchestratedSettings()
    setup_logger(settings.logging)
    
    async def _run():
        stop_event = asyncio.Event()
        setup_signals(stop_event) # Bind Docker signals
        
        nc = await setup_nats(settings.nats_host)
        manager = PredictionManager(settings, nc)
        
        try:
            # Pass stop_event to manager so it knows when to gracefully exit
            await manager.listen_to_nats(stop_event)
        finally:
            logger.info("Draining NATS connection...")
            await nc.drain()

    try:
        asyncio.run(_run())
        logger.info("Shutdown complete.")
    except Exception as e:
        logger.critical(f"System failure: {e}", exc_info=True)
        raise typer.Exit(1)

@app.command()
def bulk(
    session_dir: Annotated[Optional[Path], typer.Argument(
        help="Input Parquet file. Overrides INTENT__SESSION_PATH env var."
    )] = None,
    output_dir: Annotated[Optional[Path], typer.Option(
        "--output", "-o",
        help="Output path. Overrides INTENT__PARQUET__OUTPUT_DIR."
    )] = None,
    show_terminal_ui: Annotated[Optional[bool], typer.Option("--terminal", "-t")] = None
):
    """
    Run the engine in Offline Mode on a recorded session file.
    Uses scoring parameters from .env, but overrides Sink configuration.
    """
    settings = BulkSettings()
    setup_logger(settings.logging)

    # Override and get newly validated settings
    if show_terminal_ui is not None:
        settings.terminal.enabled = True

    if session_dir is not None:
        settings.session_path = session_dir
    elif settings.session_path is None:
        typer.secho("Error: No session directory provided via Argument or Env Var.", fg="red")
        raise typer.Exit(1)
        
    if output_dir is not None:
        settings.data_dir = output_dir
    elif settings.data_dir is None:
        typer.secho("Error: No output directory provided via Argument or Env Var.", fg="red")
        raise typer.Exit(1)
    
    settings = settings.__class__.model_validate(settings)
    logger.debug(settings)

    # Run with re-validated settings
    runner = OfflineRunner(
        session=SessionLoader(settings.session_path),
        system=IntentSystem(create_scorer_config(settings)),
        sinks=create_sinks(settings),
        playback_speed=settings.playback_speed,
        sampling_interval_ms=settings.sampling_interval_ms
    )

    try:
        asyncio.run(runner.run())
        logger.info("Processing Complete.")
    except KeyboardInterrupt:
        logger.warning("Interrupted.")
    except Exception as e:
        logger.critical(f"Critical Failure: {e}", exc_info=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()