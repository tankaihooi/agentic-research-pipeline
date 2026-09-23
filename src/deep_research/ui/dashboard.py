"""Live terminal dashboard for a research run.

`DashboardState` folds the `AgentEvent` stream into counters (pure, testable). `Dashboard` renders
that state with Rich. The same events drive a live run and `research replay`, so what you see
while filming is exactly what the agents did.

    ┌ header: prompt · pipeline stages · time and cost budget ─────────────────────┐
    ├ agents: status, current activity, counters ─┬ evidence: funnel · verdicts ───┤
    └ log: latest events, colour-coded by agent ─────────────────────────────────┘
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.layout import Layout
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from deep_research.models import Agent, AgentEvent, Stage, utcnow

PIPELINE = [
    Stage.PLANNING,
    Stage.RESEARCHING,
    Stage.VERIFYING,
    Stage.WRITING,
    Stage.AUDITING,
    Stage.DONE,
]
STAGE_AGENT = {
    Stage.PLANNING: Agent.PLANNER,
    Stage.RESEARCHING: Agent.SCRAPER,
    Stage.VERIFYING: Agent.CRITIC,
    Stage.WRITING: Agent.WRITER,
    Stage.AUDITING: Agent.AUDITOR,
}
AGENTS = [Agent.PLANNER, Agent.SCRAPER, Agent.CRITIC, Agent.WRITER, Agent.AUDITOR]
COLOR = {
    Agent.ORCHESTRATOR: "white",
    Agent.PLANNER: "magenta",
    Agent.SCRAPER: "cyan",
    Agent.CRITIC: "yellow",
    Agent.WRITER: "green",
    Agent.AUDITOR: "blue",
}
KIND_STYLE = {
    "critic.reject": "red",
    "critic.contradict": "dark_orange",
    "critic.gap": "bold magenta",
    "audit.flag": "red",
    "scrape.error": "red",
    "scrape.skip": "dim",
    "stage": "bold white",
    "research.done": "bold white",
    "critic.done": "bold yellow",
    "writer.done": "bold green",
}
HIDDEN_KINDS = {"usage"}
# A node's `stage` update only arrives when the node finishes, so on its own the pipeline marker
# would lag one step behind what is on screen. Each agent event therefore also sets the stage it
# belongs to; explicit stage events (and older logs without them) stay consistent with this.
INFERRED_STAGE = {
    "plan": Stage.PLANNING,
    "scrape": Stage.RESEARCHING,
    "critic": Stage.VERIFYING,
    "writer": Stage.WRITING,
    "audit": Stage.AUDITING,
}


@dataclass
class AgentStatus:
    events: int = 0
    last_message: str = ""


@dataclass
class DashboardState:
    prompt: str = ""
    run_id: str = ""
    depth: str = ""
    deadline_s: int = 0
    max_cost_usd: float = 0.0
    started: datetime | None = None
    clock: datetime | None = None  # replay drives a virtual clock; live runs use wall time
    replay_speed: float = 0.0  # set by `research replay`, so every frame says it is a recording
    stage: Stage = Stage.PLANNING
    last_agent: Agent | None = None
    agents: dict[Agent, AgentStatus] = field(
        default_factory=lambda: {a: AgentStatus() for a in AGENTS}
    )
    log: deque[AgentEvent] = field(default_factory=lambda: deque(maxlen=300))

    questions: int = 0
    gap_queries: int = 0
    pages_read: int = 0
    raw_tokens: int = 0
    clean_tokens: int = 0
    distilled_tokens: int = 0
    findings: int = 0
    verified: int = 0
    first_party: int = 0
    single_source: int = 0
    contradicted: int = 0
    rejected: int = 0
    sections_planned: int = 0
    sections_drafted: int = 0
    revisions: int = 0
    audit_rounds: list[tuple[int, int]] = field(default_factory=list)  # (checked, flagged)
    words: int = 0
    references: int = 0
    cost_usd: float = 0.0
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def finished(self) -> bool:
        return self.stage is Stage.DONE

    def now(self) -> datetime:
        return self.clock or utcnow()

    @property
    def elapsed_s(self) -> float:
        return (self.now() - self.started).total_seconds() if self.started else 0.0

    def apply(self, e: AgentEvent) -> None:
        d = e.data
        if self.started is None:
            self.started = e.ts
        match e.kind:
            case "run.start" | "run.resume":
                self.prompt = d.get("prompt", self.prompt)
                self.run_id = d.get("run_id", self.run_id)
                self.depth = d.get("depth", self.depth)
                self.deadline_s = d.get("deadline_s", self.deadline_s)
                self.max_cost_usd = d.get("max_cost_usd", self.max_cost_usd)
            case "stage":
                self.stage = Stage(d["stage"])
            case "usage":
                self.cost_usd = d.get("cost_usd", self.cost_usd)
                self.llm_calls = d.get("llm_calls", self.llm_calls)
                self.tokens_in = d.get("input_tokens", self.tokens_in)
                self.tokens_out = d.get("output_tokens", self.tokens_out)
            case "plan.query":
                self.questions += 1
            case "critic.gap":
                self.gap_queries += 1
            case "scrape.read":
                self.pages_read += 1
                self.raw_tokens += d.get("raw_tokens", 0)
                self.clean_tokens += d.get("tokens", 0)
            case "scrape.extract":
                self.findings += d.get("findings", 0)
            case "research.done":
                self.distilled_tokens = d.get("distilled_tokens", self.distilled_tokens)
            case "critic.reject":
                self.rejected += 1
            case "critic.summary" if d.get("check") == "cross_reference":
                self.verified += d.get("verified", 0)
                self.first_party += d.get("first_party", 0)
                self.single_source += d.get("single_source", 0)
                self.contradicted += d.get("contradicted", 0)
            case "writer.outline":  # a rewrite starts the writing stage over
                self.sections_planned = self.sections_drafted = self.revisions = 0
                self.audit_rounds = []
            case "writer.section_plan":
                self.sections_planned += 1
            case "writer.drafted":
                self.sections_drafted += 1
            case "writer.revise":
                self.revisions += 1
            case "audit.summary":
                self.audit_rounds.append((d.get("checked", 0), d.get("flagged", 0)))
            case "writer.done":
                self.words = d.get("words", 0)
                self.references = d.get("references", 0)
            case _:
                pass
        if e.kind == "writer.done":
            self.stage = Stage.DONE
        elif inferred := INFERRED_STAGE.get(e.kind.split(".", 1)[0]):
            self.stage = inferred
        if e.kind in HIDDEN_KINDS:
            return
        self.log.append(e)
        if e.agent in self.agents:
            status = self.agents[e.agent]
            status.events += 1
            status.last_message = e.message
            self.last_agent = e.agent

    def agent_state(self, agent: Agent) -> str:
        """'active', 'done' or 'idle'. One agent is active: whoever spoke last."""
        current = self.last_agent or STAGE_AGENT.get(self.stage)
        if not self.finished and agent is current:
            return "active"
        return "done" if self.agents[agent].events else "idle"

    def counters(self, agent: Agent) -> str:
        match agent:
            case Agent.PLANNER:
                extra = f" +{self.gap_queries} follow-up" if self.gap_queries else ""
                return f"{self.questions} questions{extra}"
            case Agent.SCRAPER:
                return f"{self.pages_read} pages · {self.findings} findings"
            case Agent.CRITIC:
                return (
                    f"[green]{self.verified}✓[/] [blue]{self.single_source}◐[/] "
                    f"[dark_orange]{self.contradicted}⚠[/] [red]{self.rejected}✗[/]"
                )
            case Agent.WRITER:
                revised = f" · {self.revisions} revised" if self.revisions else ""
                return f"{self.sections_drafted}/{self.sections_planned} sections{revised}"
            case Agent.AUDITOR:
                if not self.audit_rounds:
                    return "—"
                checked = self.audit_rounds[0][0]
                flags = " → ".join(str(f) for _, f in self.audit_rounds)
                return f"flagged {flags} of {checked}"
            case _:
                return ""


# ---------------------------------------------------------------------------- rendering


def _mmss(seconds: float) -> str:
    seconds = max(int(seconds), 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _truncate(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: max(width - 1, 0)] + "…"


def render_header(state: DashboardState) -> Panel:
    pipeline = Text()
    current = PIPELINE.index(state.stage)
    for i, stage in enumerate(PIPELINE):
        label = f" {stage.value.capitalize()} "
        if i < current or (state.finished and stage is Stage.DONE):
            pipeline.append(f"✓{label}", style="green")
        elif i == current:
            pipeline.append(f"▶{label}", style="bold black on yellow")
        else:
            pipeline.append(f" {label}", style="dim")
        if i < len(PIPELINE) - 1:
            pipeline.append(" \u203a ", style="bright_black")

    budget = Table.grid(padding=(0, 1))
    budget.add_column(width=17)
    budget.add_column(ratio=1)
    budget.add_column(width=19)
    budget.add_column(ratio=1)
    deadline = state.deadline_s or 1
    cap = state.max_cost_usd or 1.0
    budget.add_row(
        f"⏱ {_mmss(state.elapsed_s)} / {_mmss(deadline)}",
        ProgressBar(total=deadline, completed=min(state.elapsed_s, deadline), width=None),
        f"$ {state.cost_usd:.3f} / {cap:.2f}",
        ProgressBar(total=cap, completed=min(state.cost_usd, cap), width=None),
    )
    title = Text.assemble(("◆ DEEP RESEARCH ", "bold"), (f"{state.depth} · {state.run_id}", "dim"))
    if state.replay_speed:
        title.append(f"  ▶ REPLAY {state.replay_speed:g}\u00d7 ", style="bold black on magenta")
    body = Group(Text(state.prompt or "…", style="bold"), pipeline, budget)
    return Panel(body, title=title, title_align="left", border_style="bright_black")


def render_agents(state: DashboardState, width: int) -> Panel:
    table = Table.grid(padding=(0, 1), expand=True)
    table.add_column(width=2)
    table.add_column(width=9)
    table.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    table.add_column(width=26, justify="right", no_wrap=True)
    activity_width = max(width - 46, 20)
    for agent in AGENTS:
        status = state.agent_state(agent)
        icon = (
            Spinner("dots", style=COLOR[agent])
            if status == "active"
            else Text("✓", style="green")
            if status == "done"
            else Text("·", style="dim")
        )
        name = Text(agent.value.capitalize(), style=f"bold {COLOR[agent]}")
        message = state.agents[agent].last_message or ("waiting" if status == "idle" else "")
        activity = Text(
            _truncate(message, activity_width), style="" if status == "active" else "dim"
        )
        table.add_row(icon, name, activity, Text.from_markup(state.counters(agent)))
    return Panel(table, title="Agents", title_align="left", border_style="bright_black")


def _split_width(values: list[int], width: int) -> list[int]:
    """Share `width` cells between `values` (largest remainder), always summing to `width`."""
    total = sum(values)
    if not total:
        return [0] * len(values)
    exact = [width * v / total for v in values]
    cells = [int(x) for x in exact]
    by_remainder = sorted(range(len(values)), key=lambda i: exact[i] - cells[i], reverse=True)
    for i in by_remainder[: width - sum(cells)]:
        cells[i] += 1
    return cells


def _bar(value: int, total: int, width: int, style: str) -> Text:
    filled = round(width * value / total) if total else 0
    return Text("█" * filled, style=style) + Text("░" * (width - filled), style="bright_black")


def render_evidence(state: DashboardState) -> Panel:
    grid = Table.grid(padding=(0, 1))
    grid.add_column(width=11)
    grid.add_column(width=18)
    grid.add_column(justify="right")
    top = max(state.raw_tokens, 1)
    for label, value, style in (
        ("raw read", state.raw_tokens, "cyan"),
        ("cleaned", state.clean_tokens, "cyan"),
        ("distilled", state.distilled_tokens, "yellow"),
    ):
        grid.add_row(label, _bar(value, top, 18, style), f"{value:,} tok")

    parts = [
        (state.verified, "green"),
        (state.single_source, "blue"),
        (state.contradicted, "dark_orange"),
        (state.rejected, "red"),
    ]
    judged = sum(value for value, _ in parts)
    verdicts = Text()
    for width, (_, style) in zip(
        _split_width([value for value, _ in parts], 18), parts, strict=True
    ):
        verdicts.append("█" * width, style=style)
    grid.add_row("verdicts", verdicts, f"{judged} judged")
    grid.add_row("LLM calls", Text(f"{state.llm_calls}"), f"{state.tokens_in:,} in")
    if state.words:
        grid.add_row("report", Text(f"{state.words:,} words"), f"{state.references} sources")
    return Panel(grid, title="Evidence", title_align="left", border_style="bright_black")


class LogView:
    """Latest events that fit the available height, oldest at the top."""

    def __init__(self, state: DashboardState) -> None:
        self.state = state

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        height = (options.height or console.size.height) - 2
        width = options.max_width - 4
        events = list(self.state.log)[-max(height, 1) :]
        lines = Text()
        start = self.state.started
        for i, e in enumerate(events):
            offset = (e.ts - start).total_seconds() if start else 0.0
            style = KIND_STYLE.get(e.kind, "")
            line = Text.assemble(
                (f"+{_mmss(offset)} ", "bright_black"),
                (f"{e.agent.value.upper():>12}  ", f"bold {COLOR[e.agent]}"),
                (_truncate(e.message, max(width - 21, 10)), style),
            )
            lines.append(line)
            if i < len(events) - 1:
                lines.append("\n")
        yield Panel(
            lines,
            title="Activity",
            title_align="left",
            border_style="bright_black",
            height=options.height,  # fill the region so the frame doesn't jump as lines arrive
        )


class Dashboard:
    def __init__(self, state: DashboardState) -> None:
        self.state = state

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        width = options.max_width
        layout = Layout()
        layout.split_column(
            Layout(render_header(self.state), size=5),
            Layout(name="middle", size=8),
            Layout(LogView(self.state), name="log"),
        )
        layout["middle"].split_row(
            Layout(render_agents(self.state, int(width * 0.62)), ratio=62),
            Layout(render_evidence(self.state), ratio=38),
        )
        yield layout
