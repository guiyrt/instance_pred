from importlib.metadata import version
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PositiveInt, PositiveFloat
from typing import Optional

from .scores import ScoreSettings
from .sinks import BaseParquetSinkConfig, ServerParquetSinkConfig, BulkParquetSinkConfig, TerminalSinkConfig, NATSSinkConfig
from .utils import LoggingConfig

# <<< General app settings >>>
class AppSettings(BaseSettings):
    # Intent
    scores: ScoreSettings = Field(default_factory=ScoreSettings)
    sampling_interval_ms: PositiveInt = 100
    
    # Sinks
    parquet: BaseParquetSinkConfig
    nats: NATSSinkConfig = Field(default_factory=NATSSinkConfig)
    terminal: TerminalSinkConfig = Field(default_factory=TerminalSinkConfig)

    # Logging
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    __version__: str = version("instance-pred")

    # Pydantic will look for e.g. INTENT__SAMPLING_INTERVAL_MS
    model_config = SettingsConfigDict(
        env_prefix="INTENT__",
        env_file=".env",
        env_nested_delimiter="__", 
        case_sensitive=False
    )

# <<< App settings for running in server >>>
class ServerSettings(AppSettings):
    parquet: ServerParquetSinkConfig = Field(default_factory=ServerParquetSinkConfig)
    nats_host: str = "nats://localhost:4222"

# <<< Base offline settings, plus specific for bulk and playback executions
class OfflineSettings(AppSettings):
    session_path: Optional[Path] = None
    playback_speed: Optional[PositiveFloat]

class BulkSettings(OfflineSettings):
    parquet: BulkParquetSinkConfig = Field(default_factory=BulkParquetSinkConfig)
    playback_speed: Optional[PositiveFloat] = None

class PlaybackSettings(OfflineSettings):
    parquet: ServerParquetSinkConfig = Field(default_factory=ServerParquetSinkConfig)
    playback_speed: Optional[PositiveFloat] = 1.0