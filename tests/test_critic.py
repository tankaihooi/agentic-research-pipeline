# pyright: reportTypedDictNotRequiredAccess=false
from __future__ import annotations

import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from qdrant_client import AsyncQdrantClient

from deep_research.agents import critic
from deep_research.agents.critic import (
    CrossRefBatch,
    CrossRefJudgment,
    EntailmentBatch,
    EntailmentJudgment,
    budget_stop_reason,
    coverage,
    critic_assess,
    is_first_party,
    verify,
)
from deep_research.config import PRESETS, Depth, Settings
from deep_research.events import capture_events
from deep_research.graph.state import ResearchState
from deep_research.memory.vector_store import VectorStore
from deep_research.models import (
    Agent,
    AgentUsage,
    Finding,
    FindingCategory,
    Source,
    Stage,
    SubQuery,
    Usage,
    Verdict,
    VerdictStatus,
    stable_id,
    utcnow,
)
from tests.fakes import FakeLLM

STRIPE_PAGE = (
    "# Stripe Billing pricing\n\nStripe Billing costs 0.7% of billing volume on the pay-as-you-go "
    "plan. Usage-based billing supports meters that aggregate events per billing period."
)
BLOG_PAGE = (
    "# Review of billing tools\n\nIn our review, Stripe Billing charges 0.7% of billing volume. "
    "Chargebee offers a free Launch plan for companies below $250K in revenue."
)
OTHER_PAGE = "# Chargebee pricing\n\nChargebee Launch is free up to $250K of annual billing."


def _source(url: str, *, primary: bool) -> Source:
    sid = stable_id("S", url)
    domain = url.split("/")[2]
    return Source(
        id=sid,
        url=url,
        title=domain,
        domain=domain,
        sub_query_id="Q1",
        fetched_at=utcnow(),
        is_primary=primary,
        token_count=50,
        text_path=f"sources/{sid}.md",
    )


def _finding(source: Source, claim: str, quote: str, entity: str, q: str = "Q1") -> Finding:
    return Finding(
        id=stable_id("F", source.id, claim),
        sub_query_id=q,
        source_id=source.id,
        claim=claim,
        quote=quote,
        entity=entity,
        category=FindingCategory.PRICING,
    )


class Fixture(SimpleNamespace):
    stripe: Source
    blog: Source
    other: Source
    store: VectorStore
    run_dir: Path


@pytest.fixture
async def fx(tmp_path: Path) -> Fixture:
    stripe = _source("https://stripe.com/billing/pricing", primary=True)
    blog = _source("https://reviews.example.com/billing", primary=False)
    other = _source("https://chargebee.com/pricing", primary=True)
    (tmp_path / "sources").mkdir()
    llm = FakeLLM(dims=32)
    store = VectorStore(
        Settings(embedding_dims=32), llm, client=AsyncQdrantClient(location=":memory:")
    )
    await store.setup()
    for src, text in ((stripe, STRIPE_PAGE), (blog, BLOG_PAGE), (other, OTHER_PAGE)):
        (tmp_path / src.text_path).write_text(text)
        await store.index_source(src, text, agent=Agent.SCRAPER)
    return Fixture(stripe=stripe, blog=blog, other=other, store=store, run_dir=tmp_path)


def _ids(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\[(F-[0-9a-f]{8})\]", text)))


def _entail_all(verdict: str = "supported", overrides: dict[str, str] | None = None):
    def respond(_: str, text: str) -> EntailmentBatch:
        return EntailmentBatch(
            judgments=[
                EntailmentJudgment(
                    finding_id=f"[{fid}]",  # models sometimes echo the brackets
                    verdict=(overrides or {}).get(fid, verdict),  # type: ignore[arg-type]
                    reason="quote says 0.7%, claim says 0.8%",
                )
                for fid in _ids(text)
            ]
        )

    return respond


def _xref(verdict: str, source_ids: list[str]):
    def respond(_: str, text: str) -> CrossRefBatch:
        return CrossRefBatch(
            judgments=[
                CrossRefJudgment(
                    finding_id=fid,
                    verdict=verdict,  # type: ignore[arg-type]
                    source_ids=source_ids,
                    reason="same fact",
                )
                for fid in _ids(text)
            ]
        )

    return respond


# ------------------------------------------------------------------ grounding


async def test_fabricated_quote_is_rejected_without_any_llm_call(fx: Fixture) -> None:
    fake = _finding(
        fx.stripe,
        "Stripe Billing includes a built-in CPQ module.",
        "Stripe Billing includes a built-in CPQ module with AI-generated quotes.",
        "Stripe Billing",
    )
    llm = FakeLLM(dims=32)  # no scripted responses: any LLM call would raise
    verdicts, _ = await verify(llm, fx.store, fx.run_dir, [fake], [fx.stripe])

    v = verdicts[fake.id]
    assert v.status is VerdictStatus.REJECTED
    assert v.caught_by == "grounding"
    assert v.grounding_score is not None and v.grounding_score < 85
    assert llm.calls == []


# ------------------------------------------------------------------ entailment


async def test_entailment_rejects_distorted_claim_and_missing_judgments(fx: Fixture) -> None:
    good = _finding(
        fx.stripe,
        "Stripe Billing costs 0.7% of billing volume on pay-as-you-go.",
        "Stripe Billing costs 0.7% of billing volume on the pay-as-you-go plan.",
        "Stripe Billing",
    )
    distorted = _finding(
        fx.stripe,
        "Stripe Billing costs 0.8% of billing volume.",
        "Stripe Billing costs 0.7% of billing volume on the pay-as-you-go plan.",
        "Stripe Billing",
    )
    llm = FakeLLM(
        dims=32,
        responses={EntailmentBatch: _entail_all(overrides={distorted.id: "partially_supported"})},
    )
    verdicts, usage = await verify(llm, fx.store, fx.run_dir, [good, distorted], [fx.stripe])

    assert verdicts[distorted.id].status is VerdictStatus.REJECTED
    assert verdicts[distorted.id].caught_by == "entailment"
    assert "overstates" in verdicts[distorted.id].reasons[0]
    # the good one is first-party (Stripe on stripe.com), so it is verified with no xref call
    assert verdicts[good.id].status is VerdictStatus.VERIFIED
    assert verdicts[good.id].first_party
    assert llm.calls_for(CrossRefBatch) == []
    assert usage.by_agent[Agent.CRITIC].calls == 1  # one batched entailment call for one source


async def test_missing_entailment_judgment_is_a_rejection(fx: Fixture) -> None:
    f = _finding(fx.stripe, "Meters aggregate events.", "meters that aggregate events", "Stripe")
    llm = FakeLLM(dims=32, responses={EntailmentBatch: EntailmentBatch(judgments=[])})
    verdicts, _ = await verify(llm, fx.store, fx.run_dir, [f], [fx.stripe])
    assert verdicts[f.id].caught_by == "entailment"


# ------------------------------------------------------------------ cross-reference


def _third_party_claim(fx: Fixture) -> Finding:
    return _finding(
        fx.blog,
        "Chargebee offers a free Launch plan below $250K in revenue.",
        "Chargebee offers a free Launch plan for companies below $250K in revenue.",
        "Chargebee",
    )


@pytest.mark.parametrize(
    ("xref_verdict", "cite", "expected"),
    [
        ("corroborated", "other", VerdictStatus.VERIFIED),
        ("contradicted", "other", VerdictStatus.CONTRADICTED),
        ("no_evidence", None, VerdictStatus.SINGLE_SOURCE),
        ("corroborated", "made-up", VerdictStatus.SINGLE_SOURCE),  # cited a source it wasn't shown
    ],
)
async def test_cross_reference_outcomes(
    fx: Fixture, xref_verdict: str, cite: str | None, expected: VerdictStatus
) -> None:
    claim = _third_party_claim(fx)
    cited = {"other": [fx.other.id], "made-up": ["S-deadbeef"], None: []}[cite]
    llm = FakeLLM(
        dims=32,
        responses={EntailmentBatch: _entail_all(), CrossRefBatch: _xref(xref_verdict, cited)},
    )
    sources = [fx.stripe, fx.blog, fx.other]
    verdicts, _ = await verify(llm, fx.store, fx.run_dir, [claim], sources)
    v = verdicts[claim.id]
    assert v.status is expected
    if expected is VerdictStatus.VERIFIED:
        assert v.corroborating_source_ids == [fx.other.id]
    if expected is VerdictStatus.CONTRADICTED:
        assert v.contradicting_source_ids == [fx.other.id]
    # the claim's own source is never offered as independent evidence
    xref_input = llm.calls_for(CrossRefBatch)[0].input
    assert f"[{fx.blog.id}]" not in xref_input


def test_first_party_needs_primary_domain_and_matching_entity(fx: Fixture) -> None:
    assert is_first_party("Stripe Billing", fx.stripe)
    assert not is_first_party("Chargebee", fx.stripe)  # Stripe's page talking about a competitor
    assert not is_first_party("Stripe Billing", fx.blog)  # not the vendor's own site


# ------------------------------------------------------------------ coverage & budgets


def _verdict(fid: str, status: VerdictStatus) -> Verdict:
    return Verdict(finding_id=fid, status=status)


def test_coverage_rolls_gap_queries_up_to_their_root(fx: Fixture) -> None:
    queries = [
        SubQuery(id="Q1", question="q1", search_terms=["a"], rationale=""),
        SubQuery(id="Q1.g1", question="q1 gap", search_terms=["b"], rationale="", origin="gap"),
    ]
    statuses = [VerdictStatus.VERIFIED] * 4 + [
        VerdictStatus.SINGLE_SOURCE,
        VerdictStatus.CONTRADICTED,
        VerdictStatus.REJECTED,
    ]
    fs = [
        _finding(
            fx.stripe if i < 3 else fx.blog,
            f"claim {i}",
            "q",
            "Stripe",
            q="Q1" if i < 3 else "Q1.g1",
        )
        for i in range(len(statuses))
    ]
    verdicts = {f.id: _verdict(f.id, st) for f, st in zip(fs, statuses, strict=True)}
    [c] = coverage(queries, fs, verdicts, [fx.stripe, fx.blog])
    assert (c.query.id, c.usable, c.verified) == ("Q1", 6, 4)
    assert c.sites == {"stripe.com", "example.com"}
    assert not c.weak


def test_single_site_evidence_is_weak_however_plentiful(fx: Fixture) -> None:
    q = SubQuery(id="Q1", question="q", search_terms=["a"], rationale="")
    fs = [_finding(fx.stripe, f"claim {i}", "q", "Stripe") for i in range(10)]
    verdicts = {f.id: _verdict(f.id, VerdictStatus.VERIFIED) for f in fs}
    [c] = coverage([q], fs, verdicts, [fx.stripe])
    assert c.problems == ["all evidence comes from stripe.com"]


def _state(**overrides: Any) -> ResearchState:
    preset = PRESETS[Depth.STANDARD]
    now = time.time()
    base: ResearchState = {
        "prompt": "p",
        "depth": Depth.STANDARD,
        "started_at": now,
        "deadline": now + preset.deadline_s,
        "gap_loops": 0,
    }
    return {**base, **overrides}  # type: ignore[return-value]


def test_budget_allows_first_gap_loop() -> None:
    assert budget_stop_reason(_state()) is None


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"gap_loops": 1}, "gap-loop limit"),
        ({"deadline": time.time() + 30}, "time budget"),
        (
            {"usage": Usage.single(Agent.SCRAPER, AgentUsage(cost_usd=1.0))},
            "cost budget",
        ),
    ],
)
def test_budget_blocks_gap_loop(overrides: dict[str, Any], expected: str) -> None:
    reason = budget_stop_reason(_state(**overrides))
    assert reason is not None and reason.startswith(expected)


async def test_expired_deadline_skips_gap_loop_even_when_coverage_is_weak(fx: Fixture) -> None:
    q = SubQuery(id="Q1", question="q", search_terms=["t"], rationale="")
    state = _state(sub_queries=[q], findings=[], verdicts={}, deadline=time.time() - 1)
    llm = FakeLLM(dims=32)  # would raise if the critic tried to plan gap queries
    runtime = SimpleNamespace(context=SimpleNamespace(llm=llm))
    with capture_events() as events:
        update = await critic_assess(state, runtime)  # type: ignore[arg-type]
    assert update["stage"] is Stage.WRITING
    assert update["stop_reason"].startswith("time budget")
    assert "sub_queries" not in update
    assert any(e.kind == "critic.coverage" and "needs more evidence" in e.message for e in events)
    assert llm.calls == []


def test_constants_are_consistent() -> None:
    assert 0 < critic.GAP_TIME_FRACTION < 1
    assert critic.MIN_VERIFIED_PER_QUERY <= critic.MIN_USABLE_PER_QUERY
