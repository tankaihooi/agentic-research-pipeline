"""The top-level research graph.

    planner --Send x N--> research (scraper subgraph, parallel) --> join_research --> ...

Later phases extend this with the Critic, its gap-fill loop back into `research`, the Writer
fan-out, and the final audit.
"""

from __future__ import annotations

from datetime import UTC, datetime

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy, Send

from deep_research.agents.planner import plan
from deep_research.config import PRESETS, Depth
from deep_research.deps import Deps
from deep_research.events import emit
from deep_research.graph.scraper_graph import build_scraper_graph
from deep_research.graph.state import ResearchState
from deep_research.models import Agent, Stage
from deep_research.tools.text import count_tokens


def fan_out_research(state: ResearchState) -> list[Send]:
    preset = PRESETS[state.get("depth", Depth.STANDARD)]
    started = datetime.fromtimestamp(state.get("started_at", 0.0), UTC)
    return [
        Send(
            "research",
            {
                "sub_query": q,
                "brief": state.get("brief", ""),
                "primary_domains": state.get("primary_domains", []),
                "pages_per_query": preset.pages_per_query,
                "run_started_at": started,
            },
        )
        for q in state.get("sub_queries", [])
    ]


def join_research(state: ResearchState) -> dict:
    """Barrier after the parallel scrapers: summarise what the research phase produced."""
    sources, findings = state.get("sources", []), state.get("findings", [])
    raw = sum(s.raw_token_count for s in sources)
    clean = sum(s.token_count for s in sources)
    distilled = sum(count_tokens(f"{f.claim}\n{f.quote}") for f in findings)
    emit(
        Agent.ORCHESTRATOR,
        "research.done",
        f"Research complete: {len(sources)} sources → {len(findings)} findings · "
        f"{raw:,} raw → {clean:,} clean → {distilled:,} distilled tokens",
        sources=len(sources),
        findings=len(findings),
        raw_tokens=raw,
        clean_tokens=clean,
        distilled_tokens=distilled,
        errors=len(state.get("errors", [])),
    )
    return {"stage": Stage.VERIFYING}


def build_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph[ResearchState, Deps, ResearchState, ResearchState]:
    builder = StateGraph(ResearchState, context_schema=Deps)
    builder.add_node("planner", plan, retry_policy=RetryPolicy(max_attempts=2))
    builder.add_node("research", build_scraper_graph())
    builder.add_node("join_research", join_research)

    builder.add_edge(START, "planner")
    builder.add_conditional_edges("planner", fan_out_research, ["research"])
    builder.add_edge("research", "join_research")
    builder.add_edge("join_research", END)
    return builder.compile(checkpointer=checkpointer, name="deep_research")
