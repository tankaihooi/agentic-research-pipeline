"""Execute (or resume) one research run: stream events, checkpoint, and write run artefacts.

runs/<run_id>/
  report.md       the briefing
  run.json        prompt, depth, status, LangSmith trace links
  events.jsonl    every AgentEvent, for replay
  sources/        cleaned page text the agents read
  sources.json    Source metadata
  findings.json   extracted findings
  metrics.json    per-agent tokens/cost/latency and the compression funnel
"""

from __future__ import annotations

import json
import re
import secrets
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from deep_research.config import PRESETS, Depth, Settings
from deep_research.deps import Deps, build_deps
from deep_research.events import EventLog, event_from_stream_chunk
from deep_research.graph.checkpoint import open_checkpointer
from deep_research.graph.state import ResearchState
from deep_research.graph.workflow import build_graph
from deep_research.models import Agent, AgentEvent, Stage, Usage, VerdictStatus, utcnow
from deep_research.observability import flush_traces, run_config, trace_url
from deep_research.tools.text import count_tokens

EventSink = Callable[[AgentEvent], None]


class RunInfo(BaseModel):
    run_id: str
    prompt: str
    depth: Depth
    created_at: datetime = Field(default_factory=utcnow)
    status: str = "running"
    traces: list[str] = Field(default_factory=list)  # one LangSmith trace per run/resume attempt

    def save(self, run_dir: Path) -> None:
        (run_dir / "run.json").write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, run_dir: Path) -> RunInfo:
        return cls.model_validate_json((run_dir / "run.json").read_text(encoding="utf-8"))


def new_run_id(prompt: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:32].rstrip("-")
    return f"{datetime.now():%Y%m%d-%H%M%S}-{slug}-{secrets.token_hex(2)}"


def initial_state(info: RunInfo) -> ResearchState:
    now = time.time()
    return {
        "run_id": info.run_id,
        "prompt": info.prompt,
        "depth": info.depth,
        "started_at": now,
        "deadline": now + PRESETS[info.depth].deadline_s,
        "stage": Stage.PLANNING,
        "gap_loops": 0,
    }


async def execute(
    settings: Settings,
    info: RunInfo,
    *,
    resume: bool,
    on_event: EventSink,
    deps: Deps | None = None,
    rewind_to: str | None = None,
) -> ResearchState:
    """Run, resume, or re-run a finished run from an earlier node (`rewind_to`).

    Rewinding forks the thread from the last checkpoint taken just before `rewind_to` ran, so
    for example the Writer can be re-run on stored research without scraping again.
    """
    run_dir = settings.runs_dir / info.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    owns_deps = deps is None
    deps = deps or await build_deps(settings, run_dir)
    log = EventLog(run_dir / "events.jsonl")

    def sink(event: AgentEvent) -> None:
        log.append(event)
        on_event(event)

    root_trace = uuid4()
    info.traces.append(str(root_trace))
    info.status = "running"
    info.save(run_dir)
    try:
        async with open_checkpointer(settings.runs_dir / "checkpoints.sqlite") as saver:
            graph = build_graph(saver)
            config = run_config(
                info.run_id, root_trace, info.prompt, info.depth, settings, resumed=resume
            )
            start_config = config
            if rewind_to:
                start_config = await _checkpoint_before(graph, config, rewind_to)
                _archive_report(run_dir)
            sink(_orchestrator_event("run.resume" if resume else "run.start", info, resume))
            stream = graph.astream(
                None if resume or rewind_to else initial_state(info),
                start_config,
                context=deps,
                stream_mode=["custom", "updates"],
                subgraphs=True,  # events emitted inside the scraper subgraph
                durability="sync",  # persist each step before the next, so a crash loses nothing
            )
            async for _namespace, mode, chunk in stream:
                if mode == "custom" and (event := event_from_stream_chunk(chunk)):
                    sink(event)
            snapshot = await graph.aget_state(config)  # latest checkpoint of the thread
            state: ResearchState = snapshot.values  # type: ignore[assignment]
            info.status = "interrupted" if snapshot.next else "complete"
    except BaseException:
        info.status = "interrupted"
        raise
    finally:
        info.save(run_dir)
        if owns_deps:
            await deps.aclose()

    write_artefacts(run_dir, state)
    flush_traces()
    if url := trace_url(root_trace):
        info.traces[-1] = url
        info.save(run_dir)
    return state


async def _checkpoint_before(
    graph: CompiledStateGraph[ResearchState, Deps, ResearchState, ResearchState],
    config: RunnableConfig,
    node: str,
) -> RunnableConfig:
    async for snapshot in graph.aget_state_history(config):  # newest first
        if node in snapshot.next:
            return {**config, "configurable": dict(snapshot.config.get("configurable", {}))}
    thread = config.get("configurable", {}).get("thread_id")
    raise ValueError(f"No checkpoint before '{node}' in run {thread}")


def _archive_report(run_dir: Path) -> None:
    report = run_dir / "report.md"
    if report.exists():
        report.rename(run_dir / f"report.{datetime.now():%Y%m%d-%H%M%S}.md")


def _orchestrator_event(kind: str, info: RunInfo, resume: bool) -> AgentEvent:
    verb = "Resuming" if resume else "Starting"
    return AgentEvent(
        agent=Agent.ORCHESTRATOR,
        kind=kind,
        message=f"{verb} run {info.run_id} ({info.depth.value}): {info.prompt}",
    )


def metrics(state: ResearchState) -> dict[str, Any]:
    sources, findings = state.get("sources", []), state.get("findings", [])
    usage = state.get("usage", Usage())
    raw = sum(s.raw_token_count for s in sources)
    clean = sum(s.token_count for s in sources)
    distilled = sum(count_tokens(f"{f.claim}\n{f.quote}") for f in findings)
    verdicts = state.get("verdicts", {})
    by_status = {status.value: 0 for status in VerdictStatus}
    rejected_by = {"grounding": 0, "entailment": 0, "cross_reference": 0}
    for v in verdicts.values():
        by_status[v.status.value] += 1
        if v.caught_by:
            rejected_by[v.caught_by] += 1
    usable_ids = {fid for fid, v in verdicts.items() if v.usable}
    writer_input = sum(
        count_tokens(f"{f.claim}\n{f.quote}") for f in findings if f.id in usable_ids
    )
    return {
        "run_id": state.get("run_id"),
        "elapsed_s": round(time.time() - state.get("started_at", time.time()), 1),
        "counts": {
            "sub_queries": len(state.get("sub_queries", [])),
            "sources": len(sources),
            "sources_from_cache": sum(s.from_cache for s in sources),
            "primary_sources": sum(s.is_primary for s in sources),
            "findings": len(findings),
            "errors": len(state.get("errors", [])),
        },
        "tokens": {
            "raw_scraped": raw,
            "after_cleaning": clean,
            "distilled_findings": distilled,
            "verified_for_writer": writer_input,
            "compression_ratio": round(raw / distilled, 1) if distilled else None,
        },
        "critic": {
            "verdicts": by_status,
            "first_party": sum(v.first_party for v in verdicts.values()),
            "rejected_by": rejected_by,
            "gap_loops": state.get("gap_loops", 0),
            "stop_reason": state.get("stop_reason"),
        },
        "report": {
            "sections": len(state.get("sections", [])),
            "words": len(state.get("report_md", "").split()),
            "audit_rounds": [r.model_dump() for r in state.get("audit_rounds", [])],
            "unresolved_flags": len(state.get("audit_flags", []))
            if len(state.get("audit_rounds", [])) > 1
            else 0,
            "citation_problems": state.get("citation_problems", []),
        },
        "usage": {agent.value: u.model_dump() for agent, u in usage.by_agent.items()},
        "total": usage.total.model_dump(),
    }


def write_artefacts(run_dir: Path, state: ResearchState) -> None:
    def dump(name: str, items: list[BaseModel]) -> None:
        payload = [item.model_dump(mode="json") for item in items]
        (run_dir / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    dump("sub_queries.json", list(state.get("sub_queries", [])))
    dump("sources.json", list(state.get("sources", [])))
    dump("findings.json", list(state.get("findings", [])))
    dump("errors.json", list(state.get("errors", [])))
    dump("verdicts.json", list(state.get("verdicts", {}).values()))
    dump("audit_flags.json", list(state.get("audit_flags", [])))
    if report := state.get("report_md"):
        (run_dir / "report.md").write_text(report, encoding="utf-8")
    (run_dir / "metrics.json").write_text(json.dumps(metrics(state), indent=2), encoding="utf-8")
