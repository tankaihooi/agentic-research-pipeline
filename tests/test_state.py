from __future__ import annotations

from datetime import UTC, datetime

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from deep_research.graph.state import ResearchState, merge_usage, upsert_by_id
from deep_research.models import (
    Agent,
    AgentUsage,
    Finding,
    FindingCategory,
    Source,
    Usage,
    stable_id,
)


def _finding(claim: str, source_id: str = "S-1") -> Finding:
    return Finding(
        id=stable_id("F", source_id, claim),
        sub_query_id="Q1",
        source_id=source_id,
        claim=claim,
        quote=claim,
        entity="Stripe",
        category=FindingCategory.FEATURE,
    )


def test_stable_id_is_deterministic() -> None:
    assert stable_id("F", "a", "b") == stable_id("F", "a", "b")
    assert stable_id("F", "a", "b") != stable_id("F", "ab", "")


def test_upsert_by_id_replaces_and_keeps_order() -> None:
    a, b = _finding("a"), _finding("b")
    a2 = a.model_copy(update={"quote": "updated"})
    merged = upsert_by_id([a, b], [a2])
    assert [f.id for f in merged] == [a.id, b.id]
    assert merged[0].quote == "updated"


def test_upsert_is_idempotent_on_replay() -> None:
    items = [_finding("x"), _finding("y")]
    assert upsert_by_id(upsert_by_id([], items), items) == items


def test_merge_usage_sums_per_agent() -> None:
    one = Usage.single(Agent.PLANNER, AgentUsage(calls=1, input_tokens=10, cost_usd=0.1))
    two = Usage.single(Agent.PLANNER, AgentUsage(calls=2, input_tokens=5, cost_usd=0.2))
    three = Usage.single(Agent.CRITIC, AgentUsage(calls=1, output_tokens=7))
    merged = merge_usage(merge_usage(one, two), three)
    assert merged.by_agent[Agent.PLANNER].calls == 3
    assert merged.by_agent[Agent.PLANNER].input_tokens == 15
    assert merged.total.output_tokens == 7
    assert abs(merged.total.cost_usd - 0.3) < 1e-9


async def test_parallel_send_branches_merge_through_reducers() -> None:
    """Fan out with Send like the scraper will, and check reducers merge branch updates."""

    def fan_out(state: ResearchState) -> list[Send]:
        return [Send("branch", {"prompt": q}) for q in ("alpha", "beta", "gamma")]

    async def branch(state: ResearchState) -> dict:
        q = state.get("prompt", "")
        src = Source(
            id=stable_id("S", q),
            url=f"https://example.com/{q}",
            title=q,
            domain="example.com",
            sub_query_id=q,
            fetched_at=datetime.now(UTC),
            token_count=100,
            text_path=f"sources/{q}.md",
        )
        return {
            "sources": [src],
            "findings": [_finding(f"{q} claim", src.id)],
            "usage": Usage.single(Agent.SCRAPER, AgentUsage(calls=1, input_tokens=100)),
        }

    builder = StateGraph(ResearchState)
    builder.add_node("branch", branch)
    builder.add_conditional_edges(START, fan_out, ["branch"])
    builder.add_edge("branch", END)
    graph = builder.compile()

    out = await graph.ainvoke({"prompt": "root"})
    assert len(out["sources"]) == 3
    assert len(out["findings"]) == 3
    assert out["usage"].by_agent[Agent.SCRAPER].calls == 3
