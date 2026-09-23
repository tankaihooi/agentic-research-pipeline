"""Scripted responses for FakeLLM, shared by the offline end-to-end tests.

Each responder reads the prompt it is given (finding ids, page text, section input) and returns
a plausible structured output, so the real graph runs end to end without a model.
"""

from __future__ import annotations

import re

from deep_research.agents.auditor import AuditBatch, StatementJudgment
from deep_research.agents.critic import (
    CrossRefBatch,
    CrossRefJudgment,
    EntailmentBatch,
    EntailmentJudgment,
    GapPlan,
    GapQuery,
)
from deep_research.agents.extractor import ExtractedFinding, Extraction
from deep_research.agents.planner import PlannedQuery, ResearchPlan
from deep_research.agents.writer import ExecSummary, OutlineDraft, ReportOutline, SectionDraft
from deep_research.models import FindingCategory
from tests.fakes import FakeLLM

TERMS = ["billing features 2026", "competitor billing", "billing pricing"]


def _plan(_: str, __: str) -> ResearchPlan:
    return ResearchPlan(
        brief="Compare billing features.",
        primary_entities=["Stripe"],
        primary_domains=["docs.stripe.com"],
        queries=[
            PlannedQuery(question=f"Question about {t}?", search_terms=[t], rationale="r")
            for t in [*TERMS, "an extra query the preset should drop"]
        ],
    )


def _extract(_: str, page_input: str) -> Extraction:
    match = re.search(r"FACT ([^:]+): (.+?\.)", page_input)
    assert match, "fake page must contain a FACT line"
    return Extraction(
        relevant=True,
        findings=[
            ExtractedFinding(
                claim=f"Fact {match.group(1)} holds.",
                quote=match.group(2),
                entity="Stripe",
                category=FindingCategory.FEATURE,
            )
        ],
    )


def _finding_ids(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\[(F-[0-9a-f]{8})\]", text)))


def _entail(_: str, text: str) -> EntailmentBatch:
    return EntailmentBatch(
        judgments=[
            EntailmentJudgment(finding_id=fid, verdict="supported", reason="ok")
            for fid in _finding_ids(text)
        ]
    )


def _xref(_: str, text: str) -> CrossRefBatch:
    return CrossRefBatch(
        judgments=[
            CrossRefJudgment(finding_id=fid, verdict="no_evidence", source_ids=[], reason="none")
            for fid in _finding_ids(text)
        ]
    )


def _gaps(_: str, text: str) -> GapPlan:
    return GapPlan(
        queries=[
            GapQuery(
                for_query_id=qid,
                question=f"More on {qid}?",
                search_terms=[f"gap {qid}"],
                rationale="thin",
            )
            for qid in dict.fromkeys(re.findall(r"\[(Q\d+)\]", text))
        ]
    )


def _outline(_: str, text: str) -> ReportOutline:
    ids = re.findall(r"^(F-[0-9a-f]{8}) \|", text, re.M)
    half = len(ids) // 2
    return ReportOutline(
        title="Stripe Billing: a competitive briefing",
        sections=[
            OutlineDraft(title="Capabilities", goal="What shipped?", finding_ids=ids[:half]),
            OutlineDraft(title="Market", goal="How does it compare?", finding_ids=ids[half:]),
            OutlineDraft(title="Empty", goal="dropped", finding_ids=["F-00000000"]),
        ],
    )


OVERSTATED = "Stripe dominates every billing segment worldwide"


def _section(_: str, text: str) -> SectionDraft:
    """Drafts cite every finding plus one overstated sentence; revisions delete that sentence."""
    claims = re.findall(r"^\[(F-[0-9a-f]{8})\] (.+)$", text, re.M)
    if "Flagged statements:" in text:
        current = text.split("Section:\n", 1)[1].split("\n\nFlagged statements:", 1)[0]
        return SectionDraft(markdown=current.replace(f"{OVERSTATED} [{claims[0][0]}]. ", ""))
    title = re.search(r"^This section: (.+)$", text, re.M)
    body = " ".join(f"{claim.rstrip('.')} [{fid}]." for fid, claim in claims)
    heading = title.group(1) if title else "Section"
    return SectionDraft(markdown=f"## {heading}\n\n{OVERSTATED} [{claims[0][0]}]. {body}")


def _summary(_: str, text: str) -> ExecSummary:
    first = re.search(r"\[(F-[0-9a-f]{8})\]", text)
    assert first
    return ExecSummary(bullets=[f"Stripe shipped new billing features [{first.group(1)}]."])


def _audit(_: str, text: str) -> AuditBatch:
    return AuditBatch(
        judgments=[
            StatementJudgment(
                index=int(i),
                verdict="overstated" if OVERSTATED in statement else "supported",
                problem="generalises beyond the quote" if OVERSTATED in statement else "",
            )
            for i, statement in re.findall(r"^\((\d+)\) (.+)$", text, re.M)
        ]
    )


def scripted_llm() -> FakeLLM:
    return FakeLLM(
        responses={
            ResearchPlan: _plan,
            Extraction: _extract,
            EntailmentBatch: _entail,
            CrossRefBatch: _xref,
            GapPlan: _gaps,
            ReportOutline: _outline,
            SectionDraft: _section,
            ExecSummary: _summary,
            AuditBatch: _audit,
        }
    )
