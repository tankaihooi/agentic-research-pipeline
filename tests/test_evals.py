# pyright: reportTypedDictNotRequiredAccess=false
from __future__ import annotations

from pathlib import Path

import pytest

from deep_research.agents.extractor import Extraction
from deep_research.agents.planner import ResearchPlan
from deep_research.config import Settings
from deep_research.models import (
    Finding,
    FindingCategory,
    Source,
    SubQuery,
    Verdict,
    VerdictStatus,
    stable_id,
    utcnow,
)
from evals.ablation import write_report
from evals.critic_eval import ItemResult, summarize
from evals.fixtures import SEPARATOR, Fixture, FixtureMeta, evidence_windows
from evals.plants import distort_number, swap_entity
from tests.fakes import FakeLLM
from tests.scripted import scripted_llm


def _finding(claim: str, quote: str, entity: str = "Stripe Billing") -> Finding:
    return Finding(
        id=stable_id("F", claim),
        sub_query_id="Q1",
        source_id="S-00000001",
        claim=claim,
        quote=quote,
        entity=entity,
        category=FindingCategory.PRICING,
    )


# ------------------------------------------------------------------ deterministic plants


@pytest.mark.parametrize(
    ("claim", "quote", "expected"),
    [
        ("Stripe Billing costs 0.7% of volume.", "Billing costs 0.7% of volume", "0.9%"),
        ("It launched in 2025 for all users.", "Launched in 2025", "2024"),
        ("Free below $250K in revenue.", "free below $250K", "$500K"),
        ("Supports 1,000 events per second.", "up to 1,000 events per second", "2,000"),
        ("Announced on April 29, 2026.", "on April 29, 2026", "April 22"),
        ("Shipped March 3 for all users.", "Shipped March 3", "March 10"),
    ],
)
def test_distort_number_changes_a_number_the_quote_states(
    claim: str, quote: str, expected: str
) -> None:
    result = distort_number(_finding(claim, quote))
    assert result is not None
    new_claim, _ = result
    assert expected in new_claim and new_claim != claim


def test_distort_number_skips_claims_without_a_quoted_number() -> None:
    assert distort_number(_finding("Stripe added 3 features.", "Stripe added features")) is None


def test_swap_entity_credits_another_company_the_quote_does_not_name() -> None:
    f = _finding("Stripe Billing supports hybrid pricing.", "Billing supports hybrid pricing")
    claim, other, _ = swap_entity(f, ["Stripe", "Chargebee", "Recurly"])  # type: ignore[misc]
    assert claim == "Chargebee Billing supports hybrid pricing."
    assert other == "Chargebee"
    named = _finding("Stripe beats Chargebee.", "Stripe beats Chargebee on price", "Stripe")
    assert swap_entity(named, ["Chargebee"]) is None  # the quote names the swap target


# ------------------------------------------------------------------ evidence windows


def test_evidence_windows_locate_quotes_despite_typographic_differences() -> None:
    page = (
        "Intro. "
        + "x " * 3000
        + "Chargebee Billing\u2019s catalog supports hybrid pricing \u2014 all."
    )
    windows = evidence_windows(page, ["Chargebee Billing's catalog supports hybrid pricing - all."])
    assert "catalog supports hybrid pricing" in windows


def test_evidence_windows_keep_title_quotes_and_headings_but_not_the_rest() -> None:
    far = "filler " * 2000
    page = (
        "# Stripe changelog\n\nIntro text.\n\n" + far + "\n\n## 2026-05-27\n\n"
        "- Adds billing schedules to enable prebilling\n\n" + far + "\n\nTail secret sentence."
    )
    windows = evidence_windows(page, ["Adds billing schedules to enable prebilling"], width=200)
    assert windows.startswith("# Stripe changelog")
    assert "Adds billing schedules to enable prebilling" in windows
    assert "## 2026-05-27" in windows
    assert "Tail secret sentence." not in windows
    assert SEPARATOR in windows
    assert len(windows) < len(page) / 10


# ------------------------------------------------------------------ metrics


def _item(kind: str, reference: str, status: VerdictStatus, caught_by: str | None) -> ItemResult:
    return ItemResult(
        fixture="fx",
        finding_id=f"F-{kind}-{reference}-{status}-{caught_by}",
        kind=kind,
        reference=reference,
        status=status,
        caught_by=caught_by,
        reason="",
    )


def test_summary_rates() -> None:
    rejected, verified = VerdictStatus.REJECTED, VerdictStatus.VERIFIED
    items = [
        _item("fabricated_quote", "unsupported", rejected, "grounding"),
        _item("distorted_number", "unsupported", rejected, "entailment"),
        _item("wrong_entity", "unsupported", VerdictStatus.SINGLE_SOURCE, None),
        _item("genuine", "supported", verified, None),
        _item("genuine", "supported", rejected, "entailment"),
        _item("genuine", "unsupported", rejected, "entailment"),
    ]
    s = summarize(items)
    assert s["plants"]["caught"] == {"n": 2, "of": 3, "rate": 0.667}
    assert s["plants"]["cumulative_by_layer"]["up_to_grounding"]["n"] == 1
    assert s["plants"]["cumulative_by_layer"]["up_to_entailment"]["n"] == 2
    assert s["plants"]["missed_but_hedged"] == {"single_source": 1}
    assert s["genuine"]["false_rejections"] == {"n": 1, "of": 2, "rate": 0.5}
    assert s["genuine"]["rejection_precision"] == {"n": 1, "of": 2, "rate": 0.5}


# ------------------------------------------------------------------ ablation plumbing


async def test_write_report_starts_the_real_graph_at_the_writer(tmp_path: Path) -> None:
    llm: FakeLLM = scripted_llm()
    source = Source(
        id="S-00000001",
        url="https://stripe.com/billing",
        title="Billing",
        domain="stripe.com",
        sub_query_id="Q1",
        fetched_at=utcnow(),
        token_count=10,
        text_path="sources/S-00000001.md",
    )
    findings = [
        _finding(f"Stripe fact {i} holds.", f"FACT {i}: stated on the page.") for i in range(4)
    ]
    fixture = Fixture(
        name="tiny",
        root=tmp_path,
        meta=FixtureMeta(
            name="tiny",
            source_run_id="r",
            prompt="Stripe billing",
            depth="quick",
            brief="brief",
            primary_domains=["stripe.com"],
            sub_queries=[SubQuery(id="Q1", question="q", search_terms=["t"], rationale="r")],
        ),
        sources=[source],
        findings=findings,
        live_verdicts={},
        metrics={},
    )
    verdicts = {f.id: Verdict(finding_id=f.id, status=VerdictStatus.VERIFIED) for f in findings}
    state = await write_report(
        fixture, findings, verdicts, llm, Settings(embedding_dims=16), thread="t"
    )
    assert state["report_md"].startswith("# ")
    assert state["sections"] and state["audit_rounds"]
    # first drafts are captured before the auditor's revision round replaces them
    drafts = state["first_drafts"]  # type: ignore[typeddict-item]
    assert drafts and all(d.revision == 0 for d in drafts)
    # no research node ran: the planner and extractor were never called
    assert llm.calls_for(ResearchPlan) == [] and llm.calls_for(Extraction) == []
