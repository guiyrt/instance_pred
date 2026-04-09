import sys
import logging
import nats
from pathlib import Path

from .configs import LoggingConfig
from .configs import AppSettings
from .scoring import ScorerConfig
from .sinks import PredictionSink, ParquetSink, TerminalSink, NATSSink

logger = logging.getLogger(__name__)

def create_scorer_config(settings: AppSettings) -> ScorerConfig:
    """
    Acts as an Adapter/Assembler.
    Maps the rich, nested Pydantic settings to the flat, fast RuntimeConfig.
    """
    return ScorerConfig(
        tau_rise=settings.scores.tau.rise,
        tau_decay=settings.scores.tau.decay,
        indicator_scores=settings.scores.to_indicator_map(),
        gaze_threshold_label=settings.scores.gaze_threshold.track_label,
        gaze_threshold_pos=settings.scores.gaze_threshold.track_pos,
    )

def create_sinks(
    settings: AppSettings,
    nc: nats.NATS | None = None,
    output_dir: Path | None = None
) -> list[PredictionSink]:
    sinks = []

    if settings.parquet.enabled:
        sinks.append(
            ParquetSink(
                output_dir=output_dir or settings.parquet.output_dir,
                max_time_flush_sec=settings.parquet.max_time_flush_sec,
                drop_when_full=settings.parquet.drop_when_full,
                max_buffer_size=settings.parquet.max_buffer_size,
                queue_size=settings.parquet.queue_size
            )
        )
    
    if settings.nats.enabled:
        if nc is not None:
            sinks.append(
                NATSSink(
                    nc=nc,
                    subject=settings.nats.subject
                )
            )
        else:
            ValueError("NATS sink enabled, but no NATS instance passed to factory.")

    if settings.terminal.enabled:
        if sys.stdout.isatty():
            sinks.append(
                TerminalSink(
                    refresh_per_sec=settings.terminal.refresh_per_sec
                )
            )
        else:
            logger.info("TerminalSink disabled: stdout is not a TTY (headless environment).")
    
    return sinks

def get_logger(settings: LoggingConfig) -> logging.Logger:
    logging.basicConfig(
        level=settings.level,
        format=settings.format
    )
    
    return logging.getLogger(__name__)