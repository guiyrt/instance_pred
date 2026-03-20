import asyncio
import typer
from pathlib import Path
from typing import Annotated, Optional
import logging
import nats

# --- Local Imports ---
from .configs import ServerSettings, OfflineSettings, PlaybackSettings, BulkSettings
from .session_loader import SessionLoader
from .task_instance_prediction import IntentSystem
from .runners import ServerRunner, OfflineRunner
from .factories import create_scorer_config, create_sinks, get_logger

# --- Setup CLI ---
app = typer.Typer(no_args_is_help=True, add_completion=False)

@app.command()
def serve():
    """
    Start the Real-time Prediction Server.
    Configuration is loaded strictly from environment variables.
    """
    settings = ServerSettings()
    logger = get_logger(settings)
    logger.debug(settings)
    logger.info(f"Starting Live Engine | NATS: {settings.nats_host}")

    logging.getLogger("nats").setLevel(logging.CRITICAL)

    # Reference shared for the NATSSink and to retrieve ASD/Gaze events
    shared_nc = nats.NATS()

    runner = ServerRunner(
        system=IntentSystem(create_scorer_config(settings)),
        sinks=create_sinks(settings, nc=shared_nc),
        nc=shared_nc,
        nats_host=settings.nats_host,
        sampling_interval_ms=settings.sampling_interval_ms
    )

    asyncio.run(runner.run())

@app.command()
def playback(
    session_dir: Annotated[Optional[Path], typer.Argument(
        help="Input Parquet file. Overrides INTENT__SESSION_PATH env var."
    )] = None,
    output_dir: Annotated[Optional[Path], typer.Option(
        "--output", "-o",
        help="Output path. Overrides INTENT__PARQUET__OUTPUT_DIR."
    )] = None,
    playback_speed: Annotated[Optional[float], typer.Option(
        "--speed", "-s"
    )] = None
):
    """
    Run the engine in Offline Mode, c on a recorded session file.
    """
    settings = PlaybackSettings()
    logger = get_logger(settings)
    
    # Override and get newly validated settings
    if playback_speed is not None:
        settings.playback_speed = playback_speed

    # Run with re-validated settings
    settings = _resolve_io(settings, session_dir, output_dir)
    logger.debug(settings)

    _run_offline(settings, logger)

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
    logger = get_logger(settings)
    
    # Override and get newly validated settings
    if show_terminal_ui is not None:
        settings.terminal.enabled = True

    settings = _resolve_io(settings, session_dir, output_dir)
    logger.debug(settings)

    # Run with re-validated settings
    _run_offline(settings, logger)


def _resolve_io[T: OfflineSettings](settings: T, session_dir: Optional[Path], output_dir: Optional[Path]) -> T:
    if session_dir is not None:
        settings.session_path = session_dir
    elif settings.session_path is None:
        typer.secho("Error: No session directory provided via Argument or Env Var.", fg="red")
        raise typer.Exit(1)
        
    if output_dir is not None:
        settings.parquet.output_dir = output_dir
    elif settings.parquet.output_dir is None:
        typer.secho("Error: No output directory provided via Argument or Env Var.", fg="red")
        raise typer.Exit(1)
    
    return settings.__class__.model_validate(settings)

def _run_offline(settings: OfflineSettings, logger: logging.Logger):
    """Shared logic for initializing and running the OfflineRunner."""
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