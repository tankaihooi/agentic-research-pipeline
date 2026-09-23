"""Terminal front-ends for the event stream: a plain line printer, the live dashboard, replay.

All three consume `AgentEvent`s, so a live run, a piped run and a replay of `events.jsonl` show
the same thing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from itertools import pairwise
from types import TracebackType

from rich.console import Console
from rich.live import Live
from rich.markup import escape

from deep_research.models import Agent, AgentEvent
from deep_research.ui.dashboard import HIDDEN_KINDS, Dashboard, DashboardState

AGENT_STYLE: dict[Agent, str] = {
    Agent.ORCHESTRATOR: "bold white",
    Agent.PLANNER: "bold magenta",
    Agent.SCRAPER: "bold cyan",
    Agent.CRITIC: "bold yellow",
    Agent.WRITER: "bold green",
    Agent.AUDITOR: "bold blue",
}
KIND_STYLE = {"error": "red", "reject": "red", "skip": "dim", "flag": "red"}
FRAMES_PER_SECOND = 12


class EventPrinter:
    """One colour-coded line per event: for pipes, CI logs, and `--plain`."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console(highlight=False)

    def __call__(self, event: AgentEvent) -> None:
        if event.kind in HIDDEN_KINDS:
            return
        tag = f"[{AGENT_STYLE[event.agent]}]{event.agent.value.upper():>12}[/]"
        style = next((s for k, s in KIND_STYLE.items() if event.kind.endswith(k)), "")
        body = escape(event.message)
        line = f"[dim]{event.ts:%H:%M:%S}[/] {tag}  " + (f"[{style}]{body}[/]" if style else body)
        self.console.print(line)


class LiveDashboard:
    """Full-screen dashboard, redrawn from the event loop (no background thread touches state).

    Use as an async context manager and pass the instance as the run's event sink.
    `virtual_clock=True` (replay) makes elapsed time follow event timestamps, not the wall clock.
    """

    def __init__(self, console: Console, *, virtual_clock: bool = False) -> None:
        self.state = DashboardState()
        self.virtual_clock = virtual_clock
        self._live = Live(Dashboard(self.state), console=console, screen=True, auto_refresh=False)
        self._ticker: asyncio.Task[None] | None = None

    async def __aenter__(self) -> LiveDashboard:
        self._live.start(refresh=True)
        self._ticker = asyncio.create_task(self._tick())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._ticker:
            self._ticker.cancel()
        self._live.stop()

    async def _tick(self) -> None:
        while True:  # keeps spinners and the clock moving between events
            await asyncio.sleep(1 / FRAMES_PER_SECOND)
            self._live.refresh()

    def __call__(self, event: AgentEvent) -> None:
        if self.virtual_clock:
            self.state.clock = event.ts
        self.state.apply(event)


def replay_delays(events: Sequence[AgentEvent], speed: float, max_gap_s: float) -> list[float]:
    """Seconds to wait before each event: real gaps divided by `speed`, long pauses capped."""
    delays = [0.0]
    for prev, cur in pairwise(events):
        gap = (cur.ts - prev.ts).total_seconds() / max(speed, 1e-6)
        delays.append(min(max(gap, 0.0), max_gap_s))
    return delays[: len(events)]


async def replay(
    events: Sequence[AgentEvent],
    sink: Callable[[AgentEvent], None],
    *,
    speed: float = 8.0,
    max_gap_s: float = 1.5,
) -> None:
    for delay, event in zip(replay_delays(events, speed, max_gap_s), events, strict=True):
        if delay:
            await asyncio.sleep(delay)
        sink(event)
