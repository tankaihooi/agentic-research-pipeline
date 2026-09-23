"""The top-level research graph.

planner --Send x N--> research (scraper subgraph, parallel) --> join_research
    --> critic_verify --> critic_assess --+--Send x gaps--> research   (bounded gap loop)
                                          +--> END                     (Writer: Phase 4)
"""

from __future__ import annotations

from datetime import UTC, datetime

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy, Send

from deep_research.agents.auditor import audit_sections, route_after_audit
from deep_research.agents.critic import critic_assess, critic_verify
from deep_research.agents.planner import plan
from deep_research.agents.writer import (
    fan_out_sections,
    finalize,
    revise_section,
    write_section,
    writer_outline,
)
from deep_research.config import PRESETS, Depth
from deep_research.deps import Deps
from deep_research.events import emit
from deep_research.graph.scraper_graph import build_scraper_graph
from deep_research.graph.state import ResearchState
from deep_research.models import Agent, Stage
from deep_research.tools.text import count_tokens
from deep_research.tools.urls import normalize_url


def fan_out_research(state: ResearchState) -> list[Send]:
    """One scraper branch per sub-query that has not been researched yet.

    After planning that is every question. After the Critic it is only the gap queries, and pages
    already read in this run are skipped so a gap loop brings in new evidence.
    """
    preset = PRESETS[state.get("depth", Depth.STANDARD)]
    started = datetime.fromtimestamp(state.get("started_at", 0.0), UTC)
    done = set(state.get("researched_query_ids", []))
    already_read = [normalize_url(s.url) for s in state.get("sources", [])]
    return [
        Send(
            "research",
            {
                "sub_query": q,
                "brief": state.get("brief", ""),
                "primary_domains": state.get("primary_domains", []),
                "pages_per_query": preset.pages_per_query,
                "run_started_at": started,
                "skip_urls": already_read,
            },
        )
        for q in state.get("sub_queries", [])
        if q.id not in done
    ]


def route_after_critic(state: ResearchState) -> list[Send] | str:
    """Gap queries go back to the scrapers; otherwise research is finished and writing starts."""
    return fan_out_research(state) or "writer_outline"


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
    builder.add_node("critic_verify", critic_verify, retry_policy=RetryPolicy(max_attempts=2))
    builder.add_node("critic_assess", critic_assess, retry_policy=RetryPolicy(max_attempts=2))
    llm_retry = RetryPolicy(max_attempts=2)
    builder.add_node("writer_outline", writer_outline, retry_policy=llm_retry)
    builder.add_node("write_section", write_section, retry_policy=llm_retry)
    builder.add_node("audit_sections", audit_sections, retry_policy=llm_retry)
    builder.add_node("revise_section", revise_section, retry_policy=llm_retry)
    builder.add_node("finalize", finalize, retry_policy=llm_retry)

    builder.add_edge(START, "planner")
    builder.add_conditional_edges("planner", fan_out_research, ["research"])
    builder.add_edge("research", "join_research")
    builder.add_edge("join_research", "critic_verify")
    builder.add_edge("critic_verify", "critic_assess")
    builder.add_conditional_edges(
        "critic_assess", route_after_critic, ["research", "writer_outline"]
    )
    builder.add_conditional_edges("writer_outline", fan_out_sections, ["write_section"])
    builder.add_edge("write_section", "audit_sections")
    builder.add_conditional_edges(
        "audit_sections", route_after_audit, ["revise_section", "finalize"]
    )
    builder.add_edge("revise_section", "audit_sections")
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer, name="deep_research")
