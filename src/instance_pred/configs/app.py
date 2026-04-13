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
    
    nats_host: str = "nats://localhost:4222"
    data_dir: Path = "./data"

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

class OrchestratedSettings(ServerSettings):
    health_subject: str = "intent.health.attention"
    cmds_subject: str = "intent.cmds.attention"

# <<< Base offline settings, plus specific for bulk and playback executions
class BulkSettings(AppSettings):
    parquet: BulkParquetSinkConfig = Field(default_factory=BulkParquetSinkConfig)
    session_path: Optional[Path] = None
    playback_speed: Optional[PositiveFloat]