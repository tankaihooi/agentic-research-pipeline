"""Terminal rendering of agent events.

Phase 2 prints one colour-coded line per event. The live dashboard (Phase 5) renders the same
`AgentEvent` stream.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

from deep_research.models import Agent, AgentEvent

AGENT_STYLE: dict[Agent, str] = {
    Agent.ORCHESTRATOR: "bold white",
    Agent.PLANNER: "bold magenta",
    Agent.SCRAPER: "bold cyan",
    Agent.CRITIC: "bold yellow",
    Agent.WRITER: "bold green",
    Agent.AUDITOR: "bold blue",
}
KIND_STYLE = {"error": "red", "reject": "red", "skip": "dim"}


class EventPrinter:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console(highlight=False)

    def __call__(self, event: AgentEvent) -> None:
        tag = f"[{AGENT_STYLE[event.agent]}]{event.agent.value.upper():>12}[/]"
        style = next((s for k, s in KIND_STYLE.items() if event.kind.endswith(k)), "")
        body = escape(event.message)
        line = f"[dim]{event.ts:%H:%M:%S}[/] {tag}  " + (f"[{style}]{body}[/]" if style else body)
        self.console.print(line)
