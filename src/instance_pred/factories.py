import sys
import logging

from .configs import AppSettings
from .scoring import ScorerConfig
from .sinks import PredictionSink, ParquetSink, TerminalSink

logger = logging.getLogger(__name__)

def create_scorer_config(settings: AppSettings) -> ScorerConfig:
    """
    Acts as an Adapter/Assembler.
    Maps the rich, nested Pydantic settings to the flat, fast RuntimeConfig.
    """
    return ScorerConfig(
        tau_rise=settings.scores.tau.rise,
        tau_decay=settings.scores.tau.decay,
        s_popup_opened=settings.scores.popup_opened,
        s_label_selected=settings.scores.label_selected,
        s_label_hovered=settings.scores.label_hovered,
        s_label_parked=settings.scores.label_parked,
        s_dist_measurement=settings.scores.dist_measurement,
        s_fixation_label=settings.scores.label_fixation,
        s_fixation_pos=settings.scores.pos_fixation,
        gaze_threshold_label=settings.scores.gaze_threshold.track_label,
        gaze_threshold_pos=settings.scores.gaze_threshold.track_pos,
    )

def create_sinks(
    settings: AppSettings
) -> list[PredictionSink]:
    sinks = []

    if settings.parquet.enabled:
        sinks.append(
            ParquetSink(
                output_dir=settings.parquet.output_dir,
                max_time_flush_sec=settings.parquet.max_time_flush_sec,
                drop_when_full=settings.parquet.drop_when_full,
                max_buffer_size=settings.parquet.max_buffer_size,
                queue_size=settings.parquet.queue_size
            )
        )

    if settings.terminal.enabled:
        if sys.stdout.isatty():
            sinks.append(
                TerminalSink(
                    top_n=settings.terminal.top_n,
                    refresh_per_sec=settings.terminal.refresh_per_sec
                )
            )
        else:
            logger.info("TerminalSink disabled: stdout is not a TTY (headless environment).")
    
    return sinks

def get_logger(settings: AppSettings) -> logging.Logger:
    logging.basicConfig(
        level=settings.logging.level,
        format=settings.logging.format
    )
    
    return logging.getLogger(__name__)