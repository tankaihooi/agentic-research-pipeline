"""`research` command-line entry point."""

from __future__ import annotations

import asyncio
import json
import signal
from pathlib import Path
from typing import Annotated, Any

import typer
from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from deep_research.config import PRESETS, Depth, Tier, get_settings
from deep_research.events import EventLog
from deep_research.graph.state import ResearchState
from deep_research.llm import OpenAILLM
from deep_research.models import Agent
from deep_research.observability import (
    check_langsmith,
    flush_traces,
    langsmith_project,
    tracing_enabled,
)
from deep_research.runner import RunInfo, execute, metrics, new_run_id
from deep_research.ui.terminal import EventPrinter, LiveDashboard
from deep_research.ui.terminal import replay as replay_events

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.callback()
def main() -> None:
    """Deep research: Planner, Scraper, Critic and Writer agents producing cited briefings."""
    load_dotenv(find_dotenv(usecwd=True))


PlainOption = Annotated[
    bool, typer.Option("--plain", help="Print one line per event instead of the live dashboard.")
]


@app.command()
def run(
    prompt: Annotated[str, typer.Argument(help="The research request.")],
    depth: Annotated[Depth, typer.Option(help="quick | standard | deep")] = Depth.STANDARD,
    plain: PlainOption = False,
) -> None:
    """Start a new research run."""
    info = RunInfo(run_id=new_run_id(prompt), prompt=prompt, depth=depth)
    _execute(info, resume=False, plain=plain)


@app.command()
def resume(
    run_id: Annotated[str, typer.Argument(help="Run id (the folder name under runs/).")],
    plain: PlainOption = False,
) -> None:
    """Continue an interrupted run from its last checkpoint."""
    _execute(_load_run(run_id), resume=True, plain=plain)


@app.command()
def rewrite(
    run_id: Annotated[str, typer.Argument(help="Run id of a finished run.")],
    plain: PlainOption = False,
) -> None:
    """Re-run only the writing stage on a finished run's stored research (no new scraping)."""
    _execute(_load_run(run_id), resume=False, rewind_to="writer_outline", plain=plain)


@app.command()
def replay(
    run: Annotated[
        str, typer.Argument(help="Run id, or a folder such as examples/stripe-billing.")
    ],
    speed: Annotated[float, typer.Option(help="Playback speed multiplier.")] = 8.0,
    max_gap: Annotated[float, typer.Option(help="Longest pause between events, seconds.")] = 1.5,
    hold: Annotated[float, typer.Option(help="Seconds to hold the final frame.")] = 4.0,
    plain: PlainOption = False,
) -> None:
    """Re-render a recorded run at a chosen speed (for demos and the time-lapse video)."""
    run_dir = _run_dir(run)
    info = _load_run(run)
    events = EventLog.read(run_dir / "events.jsonl")

    async def play() -> None:
        if plain or not console.is_terminal:
            await replay_events(events, EventPrinter(console), speed=speed, max_gap_s=max_gap)
            return
        async with LiveDashboard(console, virtual_clock=True) as dashboard:
            preset = PRESETS[info.depth]
            dashboard.state.prompt, dashboard.state.run_id = info.prompt, info.run_id
            dashboard.state.depth, dashboard.state.deadline_s = info.depth.value, preset.deadline_s
            dashboard.state.max_cost_usd = preset.max_cost_usd
            await replay_events(events, dashboard, speed=speed, max_gap_s=max_gap)
            await asyncio.sleep(hold)

    asyncio.run(play())
    if (run_dir / "metrics.json").exists():
        _print_summary(info, json.loads((run_dir / "metrics.json").read_text()), run_dir)


@app.command()
def show(
    run: Annotated[
        str, typer.Argument(help="Run id, or a folder such as examples/stripe-billing.")
    ],
) -> None:
    """Render a run's report in the terminal."""
    report = _run_dir(run) / "report.md"
    if not report.exists():
        console.print(f"[red]No report at {report}[/]")
        raise typer.Exit(1)
    markdown = Markdown(report.read_text(encoding="utf-8"), hyperlinks=True)
    if console.is_terminal:
        with console.pager(styles=True):
            console.print(markdown)
    else:
        console.print(markdown)


def _run_dir(run: str) -> Path:
    """A run id under runs/, or a path to any folder holding a run (e.g. examples/...)."""
    path = Path(run)
    return path if (path / "run.json").exists() else get_settings().runs_dir / run


def _load_run(run: str) -> RunInfo:
    run_dir = _run_dir(run)
    if not (run_dir / "run.json").exists():
        console.print(f"[red]No run found at {run_dir}[/]")
        raise typer.Exit(1)
    return RunInfo.load(run_dir)


def _execute(info: RunInfo, *, resume: bool, plain: bool, rewind_to: str | None = None) -> None:
    settings = get_settings()

    async def go() -> ResearchState:
        if plain or not console.is_terminal:
            sink = EventPrinter(console)
            return await execute(settings, info, resume=resume, on_event=sink, rewind_to=rewind_to)
        async with LiveDashboard(console) as dashboard:
            return await execute(
                settings, info, resume=resume, on_event=dashboard, rewind_to=rewind_to
            )

    try:
        state = asyncio.run(go())
    except KeyboardInterrupt:
        # Ctrl-C reaches both `uv` and Python, so a second SIGINT can land during shutdown.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        console.print(
            f"\n[yellow]Interrupted. Progress is checkpointed; continue with:[/] "
            f"research resume {info.run_id}"
        )
        raise typer.Exit(130) from None
    _print_summary(info, metrics(state), settings.runs_dir / info.run_id)


def _print_summary(info: RunInfo, m: dict[str, Any], run_dir: Path) -> None:
    counts, tokens, total = m["counts"], m["tokens"], m["total"]
    table = Table(title=f"Run {info.run_id} · {info.status}", show_header=False)
    table.add_row("Elapsed", f"{m['elapsed_s']}s")
    table.add_row(
        "Sources",
        f"{counts['sources']} ({counts['primary_sources']} primary, "
        f"{counts['sources_from_cache']} cached) · {counts['errors']} errors",
    )
    table.add_row("Findings", str(counts["findings"]))
    critic = m["critic"]
    verdicts, rejected_by = critic["verdicts"], critic["rejected_by"]
    table.add_row(
        "Critic",
        f"{verdicts['verified']} verified ({critic['first_party']} first-party) · "
        f"{verdicts['single_source']} single-source · {verdicts['contradicted']} contradicted · "
        f"{verdicts['rejected']} rejected (grounding {rejected_by['grounding']}, "
        f"entailment {rejected_by['entailment']})",
    )
    table.add_row(
        "Research loop", f"{critic['gap_loops']} gap loop(s) · stopped: {critic['stop_reason']}"
    )
    table.add_row(
        "Token funnel",
        f"{tokens['raw_scraped']:,} raw → {tokens['after_cleaning']:,} clean → "
        f"{tokens['distilled_findings']:,} distilled ({tokens['compression_ratio']}x smaller) → "
        f"{tokens['verified_for_writer']:,} verified for the Writer",
    )
    for agent, usage in m["usage"].items():
        table.add_row(
            f"  {agent}",
            f"{usage['calls']} LLM calls · {usage['input_tokens']:,} in / "
            f"{usage['output_tokens']:,} out · {usage['embedding_tokens']:,} embedded · "
            f"${usage['cost_usd']:.4f}",
        )
    report = m.get("report", {})
    if report.get("words"):
        rounds = " → ".join(f"{r['flagged']} flagged" for r in report["audit_rounds"])
        table.add_row(
            "Report",
            f"{report['sections']} sections · {report['words']:,} words · audit: {rounds or 'n/a'}"
            f" · {len(report['citation_problems'])} citation issue(s)",
        )
    table.add_row("Total cost", f"${total['cost_usd']:.4f}")
    table.add_row("Output", str(run_dir / "report.md") if report.get("words") else str(run_dir))
    if info.traces and info.traces[-1].startswith("http"):
        table.add_row("Trace", info.traces[-1])
    console.print(table)


class _Ping(BaseModel):
    reply: str


@app.command()
def doctor() -> None:
    """Check API keys, make one traced LLM call, and report its tokens and cost."""
    settings = get_settings()
    tracing = tracing_enabled()
    langsmith_ok, langsmith_detail = check_langsmith() if tracing else (False, "tracing disabled")
    table = Table(title="Environment", show_header=False)
    table.add_row("OPENAI_API_KEY", _ok(settings.openai_api_key is not None))
    table.add_row("TAVILY_API_KEY", _ok(settings.tavily_api_key is not None))
    table.add_row("LangSmith tracing", _ok(tracing, f"project={langsmith_project()}"))
    table.add_row("LangSmith auth", _ok(langsmith_ok, langsmith_detail))
    table.add_row("Models", f"fast={settings.fast_model}  strong={settings.strong_model}")
    console.print(table)

    if settings.openai_api_key is None:
        console.print("[red]Set OPENAI_API_KEY in .env to run the LLM smoke call.[/]")
        raise typer.Exit(1)

    async def ping() -> None:
        llm = OpenAILLM(settings)
        result = await llm.parse(
            agent=Agent.ORCHESTRATOR,
            tier=Tier.FAST,
            instructions="You are a health check. Reply with the single word: pong.",
            input="ping",
            schema=_Ping,
            name="doctor.ping",
        )
        usage = result.usage.total
        console.print(
            f"[green]LLM ok[/] model={result.model} reply={result.parsed.reply!r} "
            f"in={usage.input_tokens} out={usage.output_tokens} "
            f"latency={usage.latency_ms:.0f}ms cost=${usage.cost_usd:.6f}"
        )

    asyncio.run(ping())
    if langsmith_ok:
        flush_traces()
        console.print(f"Trace uploaded to LangSmith project [bold]{langsmith_project()}[/].")
    elif tracing:
        console.print("[yellow]Tracing is on but LangSmith rejected the key; no trace recorded.[/]")
        raise typer.Exit(1)


def _ok(flag: bool, detail: str = "") -> str:
    mark = "[green]✓[/]" if flag else "[red]✗[/]"
    return f"{mark} {detail}".rstrip()
