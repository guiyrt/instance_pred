import sys
import time
import logging
from functools import cached_property, lru_cache
from datetime import datetime, timezone
from typing import Optional, Final

from rich import box
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .base import PredictionSink
from ..scoring import InstancePrediction, ScoredAircraft

logger = logging.getLogger(__name__)


class HeaderClock:
    _RADAR_FRAMES: Final[str] = "⠁⠂⠄⡀⢀⠠⠐⠈"
    _RADAR_STATES: Final[int] = 8
    _RADAR_COLOR: Final[str] = "bold green"

    """Animates independently of data updates."""
    def __init__(self):
        self.start_time: float = time.monotonic()
        self.timestamp: datetime = datetime.fromtimestamp(0, timezone.utc)

    def __rich__(self) -> Table:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="right")

        now = time.monotonic()

        # Time
        time_info = Text.assemble(
            ("UTC: ", "bold dim"),
            (f"{self.timestamp.strftime('%d %b %Y, %H:%M:%S')} | ", "dim"),
            ("Uptime: ", "bold white"),
            (time.strftime("%H:%M:%S", time.gmtime(now - self.start_time)), "white")
        )

        # Radar
        radar_heartbeat = Text.assemble(
            ("│ ", "bright_black"),
            (self._RADAR_FRAMES[int(now * 10) % self._RADAR_STATES], self._RADAR_COLOR)
        )

        grid.add_row(time_info, radar_heartbeat)
        return grid
    

class RankingTable:
    _COLOR_DIM: Final[str] = "bright_black"
    _BAR_WIDTH: Final[int] = 20

    def __init__(self) -> None:
        self.pred: Optional[InstancePrediction] = None
        self.table: Table = self._empty_table

        # Caching markers
        self._prev_pred: Optional[InstancePrediction] = None

    def _create_base_table(self) -> Table:
        """Standardized table constructor to ensure visual consistency."""
        table = Table(expand=True, box=box.SIMPLE_HEAVY, show_header=True, border_style="dim")
        table.add_column("Rank", justify="center", width=6)
        table.add_column("Callsign", width=15)
        table.add_column("Score", justify="right", width=10)
        table.add_column("Graph", justify="left")
        table.add_column("Indicators", justify="left", width=25)
        return table

    @cached_property
    def _empty_table(self) -> Table:
        table = self._create_base_table()
        table.add_row("-", "Waiting for targets...", "-", "░"*20, style=self._COLOR_DIM)
        return table
    
    def _get_style(self, score: float, rank: int) -> str:
        if score <= 10.0:
            color = self._COLOR_DIM
        elif score <= 30.0:
            color = "yellow"
        else:
            color = "green"

        return f"bold {color}" if rank == 0 else color
    
    @lru_cache(2048)
    def _get_row(self, aircraft: ScoredAircraft, rank: int) -> tuple[Text, ...]:
        style = self._get_style(aircraft.score, rank)
        
        ind_str = ", ".join([ind.name for ind in aircraft.indicators])
        filled = int((aircraft.score / 100.0) * self._BAR_WIDTH)
        bar = "█" * filled + "░" * (self._BAR_WIDTH - filled)
        
        return (
            Text(str(rank + 1), style=style),
            Text(aircraft.callsign, style=style),
            Text(f"{aircraft.score:>5.1f}%", style=style),
            Text(bar, style=style),
            Text(ind_str, style=style)
        )

    def __rich__(self) -> Table:
        # Empty table
        if not self.pred:
            return self._empty_table
        # Same pred as before, return previous table
        elif self.pred is self._prev_pred:
            return self.table
        # New data, create new table
        else:
            self._prev_pred = self.pred
            self.table = self._create_base_table()

            # Add top candidate
            self.table.add_row(*self._get_row(self.pred.aircraft, 0))
            self.table.add_section()

            # Add remaining candidates
            for rank, aircraft in enumerate(self.pred.candidates[1:], start=1):
                self.table.add_row(*self._get_row(aircraft, rank))

        return self.table


class TerminalSink(PredictionSink):
    def __init__(self, refresh_per_sec: int = 10):
        self._isatty = sys.stdout.isatty()

        if not self._isatty:
            logger.info("TerminalSink disabled: stdout is not a TTY (headless environment).")
            return
        
        self._live: Optional[Live] = None
        self.refresh_per_sec = refresh_per_sec
        
        # State
        self.header = HeaderClock()
        self.ranks = RankingTable()
        
        # Layout Setup
        self.layout = Layout()
        self.layout.split_column(Layout(name="header", size=3), Layout(name="body"))
        self.layout["header"].update(Panel(self.header, title="System Status", border_style="blue"))
        self.layout["body"].update(Panel(self.ranks, title="Live Ranking", border_style="white"))
        
    async def send(self, pred: InstancePrediction) -> None:
        if not self._isatty or not self._live:
            return

        self.ranks.pred = pred
        self.header.timestamp = pred.timestamp_ms

    async def start(self) -> None:
        if self._isatty and self._live is None:
            self._live = Live(
                self.layout, 
                screen=True, 
                refresh_per_second=self.refresh_per_sec
            )
            self._live.start()

    async def close(self) -> None:
        if self._live:
            self._live.stop()
            self._live = None