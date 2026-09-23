"""Auditor: checks every statement in the draft against the findings it cites.

The Critic vetted the findings; the auditor vets the Writer's use of them. Writers overstate,
drop qualifiers, merge two facts into a stronger third, or cite the wrong finding. Flagged
sections go back to the Writer once. Anything still flagged after that is marked in the report,
not hidden.
"""

from __future__ import annotations

import asyncio
from typing import Literal

from langgraph.runtime import Runtime
from langgraph.types import Send
from pydantic import BaseModel, Field

from deep_research.agents.writer import fan_out_revisions
from deep_research.config import Tier
from deep_research.deps import Deps
from deep_research.events import emit
from deep_research.graph.state import ResearchState
from deep_research.llm import LLMClient
from deep_research.models import (
    Agent,
    AuditFlag,
    AuditRound,
    Finding,
    Section,
    Source,
    Stage,
    Usage,
)
from deep_research.tools.text import audit_units, cited_finding_ids, is_uncited_figure

MAX_REVISION_ROUNDS = 1


class StatementJudgment(BaseModel):
    index: int
    verdict: Literal["supported", "overstated", "unsupported"]
    problem: str = Field(description="Empty when supported; otherwise under 20 words.")


class AuditBatch(BaseModel):
    judgments: list[StatementJudgment]


AUDIT_INSTRUCTIONS = """\
You audit a research briefing for faithfulness. Each numbered statement is followed by the
findings it cites (claim plus the verbatim source quote). Judge each statement:

- supported: everything the statement asserts is backed by its cited findings.
- overstated: mostly backed, but it exaggerates, generalises, drops a qualifier ("up to", "beta",
  "in some regions", a date), or merges facts into a stronger claim than either supports.
- unsupported: it asserts something the cited findings do not say, or cites the wrong finding.

Attribution ("according to <site>", "Stripe states") is correct when it matches the finding's
source. Analysis framed as interpretation ("this suggests...") is acceptable if it follows from
the cited findings. Judge only against the findings shown. Return one judgment per statement
index.
"""


def _short(text: str, limit: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def audit_section(
    llm: LLMClient,
    section: Section,
    findings: dict[str, Finding],
    sources: dict[str, Source] | None = None,
) -> tuple[list[AuditFlag], int, Usage]:
    """Returns (flags, statements checked, usage). Usable outside the graph (eval harness)."""
    flags: list[AuditFlag] = []
    to_judge: list[tuple[str, list[str]]] = []
    for unit in audit_units(section.markdown):
        ids = list(dict.fromkeys(cited_finding_ids(unit)))
        if not ids:
            if is_uncited_figure(unit):
                flags.append(
                    AuditFlag(
                        section_id=section.id,
                        sentence=unit,
                        cited_finding_ids=[],
                        verdict="uncited",
                        problem="states a figure without a citation",
                    )
                )
            continue
        unknown = [fid for fid in ids if fid not in findings]
        if unknown:
            flags.append(
                AuditFlag(
                    section_id=section.id,
                    sentence=unit,
                    cited_finding_ids=ids,
                    verdict="unsupported",
                    problem=f"cites {unknown[0]}, which is not one of the findings",
                )
            )
            continue
        to_judge.append((unit, ids))

    usage = Usage()
    if to_judge:
        blocks = []
        for i, (unit, ids) in enumerate(to_judge, start=1):
            cited = "\n".join(_cited_block(findings[fid], (sources or {})) for fid in ids)
            blocks.append(f"({i}) {unit}\n  cites:\n{cited}")
        result = await llm.parse(
            agent=Agent.AUDITOR,
            tier=Tier.FAST,
            instructions=AUDIT_INSTRUCTIONS,
            input="\n\n".join(blocks),
            schema=AuditBatch,
            name="auditor.section",
        )
        usage = result.usage
        for j in result.parsed.judgments:
            if j.verdict == "supported" or not 1 <= j.index <= len(to_judge):
                continue
            unit, ids = to_judge[j.index - 1]
            flags.append(
                AuditFlag(
                    section_id=section.id,
                    sentence=unit,
                    cited_finding_ids=ids,
                    verdict=j.verdict,
                    problem=j.problem or j.verdict,
                )
            )
    checked = len(to_judge) + sum(f.verdict == "uncited" for f in flags)
    return flags, checked, usage


def _cited_block(finding: Finding, sources: dict[str, Source]) -> str:
    # The source site matters: "according to paddle.com" is only checkable if the auditor
    # knows which site the finding came from.
    source = sources.get(finding.source_id)
    origin = ""
    if source is not None:
        origin = f"\n    source: {source.domain}" + (
            " (vendor's own site)" if source.is_primary else ""
        )
    return f'    [{finding.id}] claim: {finding.claim}\n    quote: "{finding.quote}"{origin}'


async def audit_sections(state: ResearchState, runtime: Runtime[Deps]) -> dict:
    deps = runtime.context
    round_no = len(state.get("audit_rounds", [])) + 1
    sections = sorted(state.get("sections", []), key=lambda s: s.order)
    if round_no > 1:  # later rounds re-check only what the Writer revised
        sections = [s for s in sections if s.revision >= round_no - 1]
    findings = {f.id: f for f in state.get("findings", [])}
    sources = {s.id: s for s in state.get("sources", [])}
    emit(
        Agent.AUDITOR,
        "audit.start",
        f"Audit round {round_no}: checking every statement in {len(sections)} section(s) "
        "against the findings it cites…",
    )
    results = await asyncio.gather(
        *(audit_section(deps.llm, s, findings, sources) for s in sections)
    )
    flags = [flag for section_flags, _, _ in results for flag in section_flags]
    checked = sum(n for _, n, _ in results)
    order = {s.id: s.order + 1 for s in sections}
    for flag in flags:
        emit(
            Agent.AUDITOR,
            "audit.flag",
            f"⚑ §{order.get(flag.section_id, '?')} {flag.verdict}: {_short(flag.problem, 70)} · "
            f"“{_short(flag.sentence, 70)}”",
            section_id=flag.section_id,
        )
    will_revise = bool(flags) and round_no <= MAX_REVISION_ROUNDS
    flagged_sections = len({f.section_id for f in flags})
    emit(
        Agent.AUDITOR,
        "audit.summary",
        f"Audit round {round_no}: {checked} statements checked, {len(flags)} flagged"
        + (f" → sending {flagged_sections} section(s) back to the Writer" if will_revise else ""),
        round=round_no,
        checked=checked,
        flagged=len(flags),
    )
    return {
        "audit_flags": flags,
        "audit_rounds": [
            AuditRound(
                round=round_no,
                sections_checked=len(sections),
                statements_checked=checked,
                flagged=len(flags),
            )
        ],
        "usage": sum((u for _, _, u in results), Usage()),
        "stage": Stage.AUDITING,
    }


def route_after_audit(state: ResearchState) -> list[Send] | str:
    """Flagged sections get one revision round; after that the report is finalised."""
    if state.get("audit_flags") and len(state.get("audit_rounds", [])) <= MAX_REVISION_ROUNDS:
        return fan_out_revisions(state) or "finalize"
    return "finalize"
