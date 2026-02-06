import pandas as pd
import heapq
from pathlib import Path
from typing import Iterator
from functools import cache, cached_property

from .models import RowEvent, EventType

class SessionLoader:
    def __init__(self, session_folder: Path) -> None:
        folder: Path = session_folder / "dataframes"

        self.available_events: set[EventType] = set(
            event_type
            for event_type in EventType
            if folder.joinpath(f"{event_type.value}.parquet").exists()
        )

        self.events: dict[EventType, pd.DataFrame] = {
            event_type: pd.read_parquet(folder / f"{event_type.value}.parquet")
            for event_type in self.available_events
        }

    @cached_property
    def start_timestamp(self) -> int:
        return int(min(df.epoch_ms.min() for df in self.events.values()))

    @cached_property
    def end_timestamp(self) -> int:
        return int(max(df.epoch_ms.max() for df in self.events.values()))

    @cache  
    def __len__(self) -> int:
        """Returns total event count."""
        return sum(map(len, self.events.values()))

    def has_events(self, event: EventType) -> bool:
        return event in self.available_events

    def stream(self) -> Iterator[RowEvent]:
        def make_gen(event_type: EventType):
            df = self.events[event_type]

            if not df.epoch_ms.is_monotonic_increasing:
                df = df.sort_values("epoch_ms")

            for row in df.itertuples(index=False, name="Row"):
                yield RowEvent(event_type, row.epoch_ms, row)

        yield from heapq.merge(
            *(make_gen(event_type) for event_type in self.available_events),
            key=lambda event: event.timestamp_ms
        )