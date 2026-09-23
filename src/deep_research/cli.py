"""`research` command-line entry point."""

from __future__ import annotations

import asyncio
import signal
from typing import Annotated

import typer
from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from deep_research.config import Depth, Tier, get_settings
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
from deep_research.ui.terminal import EventPrinter

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.callback()
def main() -> None:
    """Deep research: Planner, Scraper, Critic and Writer agents producing cited briefings."""
    load_dotenv(find_dotenv(usecwd=True))


@app.command()
def run(
    prompt: Annotated[str, typer.Argument(help="The research request.")],
    depth: Annotated[Depth, typer.Option(help="quick | standard | deep")] = Depth.STANDARD,
) -> None:
    """Start a new research run."""
    info = RunInfo(run_id=new_run_id(prompt), prompt=prompt, depth=depth)
    _execute(info, resume=False)


@app.command()
def resume(
    run_id: Annotated[str, typer.Argument(help="Run id (the folder name under runs/).")],
) -> None:
    """Continue an interrupted run from its last checkpoint."""
    settings = get_settings()
    run_dir = settings.runs_dir / run_id
    if not (run_dir / "run.json").exists():
        console.print(f"[red]No run found at {run_dir}[/]")
        raise typer.Exit(1)
    _execute(RunInfo.load(run_dir), resume=True)


def _execute(info: RunInfo, *, resume: bool) -> None:
    settings = get_settings()
    try:
        state = asyncio.run(execute(settings, info, resume=resume, on_event=EventPrinter(console)))
    except KeyboardInterrupt:
        # Ctrl-C reaches both `uv` and Python, so a second SIGINT can land during shutdown.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        console.print(
            f"\n[yellow]Interrupted. Progress is checkpointed; continue with:[/] "
            f"research resume {info.run_id}"
        )
        raise typer.Exit(130) from None
    _summary(info, state, settings.runs_dir / info.run_id)


def _summary(info: RunInfo, state: ResearchState, run_dir: object) -> None:
    m = metrics(state)
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
    table.add_row("Total cost", f"${total['cost_usd']:.4f}")
    table.add_row("Output", str(run_dir))
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
