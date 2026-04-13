from typing import Self, Optional
from pathlib import Path
from pydantic import BaseModel, PositiveInt, model_validator

class BaseParquetSinkConfig(BaseModel):
    enabled: bool = True
    max_time_flush_sec: Optional[PositiveInt]
    drop_when_full: bool
    max_buffer_size: PositiveInt
    queue_size: PositiveInt

    @model_validator(mode='after')
    def validate_buffer_sizes(self) -> Self:
        if self.queue_size <= self.max_buffer_size:
            raise ValueError('Queue must be bigger than buffer.')
        return self
    
class ServerParquetSinkConfig(BaseParquetSinkConfig):
    max_time_flush_sec: Optional[PositiveInt] = 30
    drop_when_full: bool = True
    max_buffer_size: PositiveInt = 500
    queue_size: PositiveInt = 5_000

class BulkParquetSinkConfig(BaseParquetSinkConfig):
    max_time_flush_sec: Optional[PositiveInt] = None
    drop_when_full: bool = False
    max_buffer_size: PositiveInt = 50_000
    queue_size: PositiveInt = 100_000