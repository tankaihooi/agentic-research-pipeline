"""Writer: outline → parallel section drafts → (audit/revise) → final report with citations.

Each section writer sees only the findings assigned to it, plus the report brief and the other
section titles. A long report is written from several small prompts rather than one huge one, and
every factual sentence carries finding-id citations that the auditor and the citation
renumbering can check mechanically.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from datetime import date
from typing import TypedDict

from langgraph.runtime import Runtime
from langgraph.types import Send
from pydantic import BaseModel, Field

from deep_research.config import Tier
from deep_research.deps import Deps
from deep_research.events import emit
from deep_research.graph.state import ResearchState
from deep_research.models import (
    Agent,
    AuditFlag,
    Finding,
    OutlineSection,
    Section,
    Source,
    Stage,
    Verdict,
    VerdictStatus,
)
from deep_research.tools.text import (
    cited_finding_ids,
    count_tokens,
    lint_citations,
    mark_unit,
    renumber_citations,
)

MAX_FINDINGS_PER_SECTION = 40
UNRESOLVED_MARK = " †"
# "…available. [1, 2]" -> "…available [1, 2]." so every citation sits inside its sentence
CITATION_AFTER_PERIOD = re.compile(r"\.\s*(\[\d+(?:,\s*\d+)*\])(?=\s|$)")


# ---------------------------------------------------------------------------- LLM schemas


class OutlineDraft(BaseModel):
    title: str
    goal: str = Field(description="The question this section answers.")
    finding_ids: list[str]


class ReportOutline(BaseModel):
    title: str = Field(description="Specific, informative report title.")
    sections: list[OutlineDraft]


class SectionDraft(BaseModel):
    markdown: str


class ExecSummary(BaseModel):
    bullets: list[str]


OUTLINE_INSTRUCTIONS = """\
You are the Writer in a research pipeline, planning a briefing. Use ONLY the findings listed.

- Design 4-7 sections that answer the request and follow the brief. For a competitive analysis
  that usually means: the subject's new capabilities, its pricing, each major competitor or a
  head-to-head comparison, a comparison at a glance, and implications drawn from the evidence.
- Assign every relevant finding id to exactly one section, the best fit. A thorough briefing
  draws on most of the evidence (typically 60-90% of the findings); leave out only findings that
  are off-topic or add nothing. Near-duplicates can share a section: its writer merges them.
- Give each section a goal: the question it answers for the reader.
"""

SECTION_INSTRUCTIONS = """\
You are the Writer in a research pipeline. Write ONE section of a briefing in Markdown, using
ONLY the findings provided.

Rules:
- Start with "## <section title>". Length follows the evidence: roughly 300-700 words. Use
  every finding you are given unless it duplicates another. Short paragraphs, plus bullets or a
  table where they help comparison.
- Every sentence, bullet or table cell that states a fact ends with its citations: finding ids in
  square brackets, exactly as given, e.g. [F-1a2b3c4d] or [F-1a2b3c4d, F-5e6f7a8b]. Never invent
  an id. Put citations before the sentence's final period.
- State only what the cited findings say. No outside knowledge. Light synthesis is fine if it is
  framed as analysis ("This suggests...") and cites the findings it rests on.
- Respect each finding's status:
  - verified: state it plainly.
  - first-party: the vendor says it about itself. Attribute marketing or performance claims
    ("Stripe states...").
  - single-source: attribute it to its source ("According to <domain>...").
  - contradicted: say that sources disagree and give the note.
- Keep qualifiers such as "up to", "beta", "in some regions", and dates.
- Do not cover what belongs to the other sections listed.
"""

EXEC_INSTRUCTIONS = """\
Write the executive summary of this briefing: 5-7 bullets for a decision-maker, one sentence each,
covering the most important conclusions across all sections. Use only facts stated in the
sections, and end each bullet with the finding-id citations of the sentences it summarises, in
the same [F-xxxxxxxx] format. Bullets are plain sentences, without a leading dash.
"""

REVISE_INSTRUCTIONS = """\
You are the Writer revising one section after an audit. Fix ONLY the flagged statements: rewrite
each so it says exactly what its cited findings support (restore qualifiers, attribute claims,
correct the citation), or delete it if no finding supports it. Leave every other sentence,
the heading and the citation format unchanged. Return the full revised section.
"""


# ---------------------------------------------------------------------------- formatting


def usable_findings(state: ResearchState) -> list[Finding]:
    verdicts = state.get("verdicts", {})
    return [
        f for f in state.get("findings", []) if (v := verdicts.get(f.id)) is not None and v.usable
    ]


def status_label(verdict: Verdict, source: Source | None) -> str:
    if verdict.first_party:
        return f"verified · first-party ({source.domain if source else 'vendor site'})"
    return verdict.status.value.replace("_", "-")


def format_finding(f: Finding, verdict: Verdict, source: Source | None, *, full: bool) -> str:
    """One finding as the Writer sees it. `full` adds the quote and source (section writing)."""
    if not full:
        status = status_label(verdict, source)
        return f"{f.id} | {f.entity} | {f.category.value} | {status} | {f.claim}"
    lines = [
        f"[{f.id}] {f.claim}",
        f"  status: {status_label(verdict, source)}",
        f'  quote: "{f.quote}"',
    ]
    if source is not None:
        lines.append(f"  source: {source.title} ({source.domain})")
    if verdict.status is VerdictStatus.CONTRADICTED and verdict.reasons:
        lines.append(f"  note: {verdict.reasons[0]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------- outline


async def writer_outline(state: ResearchState, runtime: Runtime[Deps]) -> dict:
    deps = runtime.context
    verdicts = state.get("verdicts", {})
    sources = {s.id: s for s in state.get("sources", [])}
    findings = usable_findings(state)
    emit(
        Agent.WRITER,
        "writer.outline",
        f"Planning the report from {len(findings)} usable findings…",
        findings=len(findings),
    )
    listing = "\n".join(
        format_finding(f, verdicts[f.id], sources.get(f.source_id), full=False) for f in findings
    )
    result = await deps.llm.parse(
        agent=Agent.WRITER,
        tier=Tier.STRONG,
        instructions=OUTLINE_INSTRUCTIONS,
        input=(
            f"Request: {state['prompt']}\nBrief: {state.get('brief', '')}\n\nFindings:\n{listing}"
        ),
        schema=ReportOutline,
        name="writer.outline",
    )
    usable_ids = {f.id for f in findings}
    assigned: set[str] = set()
    outline: list[OutlineSection] = []
    for draft in result.parsed.sections:
        ids = [fid.strip(" []") for fid in draft.finding_ids]
        ids = [fid for fid in dict.fromkeys(ids) if fid in usable_ids and fid not in assigned]
        ids = ids[:MAX_FINDINGS_PER_SECTION]
        if not ids:
            continue
        assigned.update(ids)
        outline.append(
            OutlineSection(
                id=f"sec-{len(outline) + 1}", title=draft.title, goal=draft.goal, finding_ids=ids
            )
        )
    if not outline:
        raise ValueError("Writer produced an outline with no usable sections")
    for sec in outline:
        emit(
            Agent.WRITER,
            "writer.section_plan",
            f"§{sec.id.split('-')[1]} {sec.title} ({len(sec.finding_ids)} findings)",
            section_id=sec.id,
        )
    return {
        "report_title": result.parsed.title,
        "outline": outline,
        "usage": result.usage,
        "stage": Stage.WRITING,
    }


# ---------------------------------------------------------------------------- sections


class SectionTask(TypedDict):
    task_section: OutlineSection
    task_order: int
    task_findings: list[str]  # formatted findings (full)
    task_prompt: str
    task_brief: str
    task_title: str
    task_other_titles: list[str]


class RevisionTask(TypedDict):
    task_current: Section
    task_flags: list[AuditFlag]
    task_findings: list[str]


def _formatted_for(state: ResearchState, finding_ids: Sequence[str]) -> list[str]:
    by_id = {f.id: f for f in state.get("findings", [])}
    verdicts = state.get("verdicts", {})
    sources = {s.id: s for s in state.get("sources", [])}
    return [
        format_finding(by_id[fid], verdicts[fid], sources.get(by_id[fid].source_id), full=True)
        for fid in finding_ids
        if fid in by_id and fid in verdicts
    ]


def fan_out_sections(state: ResearchState) -> list[Send]:
    outline = state.get("outline", [])
    titles = [s.title for s in outline]
    return [
        Send(
            "write_section",
            {
                "task_section": sec,
                "task_order": i,
                "task_findings": _formatted_for(state, sec.finding_ids),
                "task_prompt": state["prompt"],
                "task_brief": state.get("brief", ""),
                "task_title": state.get("report_title", ""),
                "task_other_titles": [t for t in titles if t != sec.title],
            },
        )
        for i, sec in enumerate(outline)
    ]


async def write_section(state: SectionTask, runtime: Runtime[Deps]) -> dict:
    deps, sec = runtime.context, state["task_section"]
    emit(Agent.WRITER, "writer.draft", f"Drafting §{state['task_order'] + 1} {sec.title}…")
    body = "\n\n".join(state["task_findings"])
    result = await deps.llm.parse(
        agent=Agent.WRITER,
        tier=Tier.STRONG,
        instructions=SECTION_INSTRUCTIONS,
        input=(
            f"Report: {state['task_title']}\nRequest: {state['task_prompt']}\n"
            f"Brief: {state['task_brief']}\n"
            f"Other sections (do not cover): {'; '.join(state['task_other_titles'])}\n\n"
            f"This section: {sec.title}\nGoal: {sec.goal}\n\nFindings:\n{body}"
        ),
        schema=SectionDraft,
        name="writer.section",
    )
    markdown = result.parsed.markdown.strip()
    emit(
        Agent.WRITER,
        "writer.drafted",
        f"§{state['task_order'] + 1} drafted: {len(markdown.split())} words, "
        f"{len(set(cited_finding_ids(markdown)))} findings cited "
        f"(from {count_tokens(body):,} tokens of evidence)",
        section_id=sec.id,
    )
    section = Section(id=sec.id, order=state["task_order"], title=sec.title, markdown=markdown)
    return {"sections": [section], "usage": result.usage}


def fan_out_revisions(state: ResearchState) -> list[Send]:
    flags_by_section: dict[str, list[AuditFlag]] = {}
    for flag in state.get("audit_flags", []):
        flags_by_section.setdefault(flag.section_id, []).append(flag)
    outline = {s.id: s for s in state.get("outline", [])}
    sections = {s.id: s for s in state.get("sections", [])}
    return [
        Send(
            "revise_section",
            {
                "task_current": sections[sid],
                "task_flags": flags,
                "task_findings": _formatted_for(state, outline[sid].finding_ids),
            },
        )
        for sid, flags in flags_by_section.items()
        if sid in sections and sid in outline
    ]


async def revise_section(state: RevisionTask, runtime: Runtime[Deps]) -> dict:
    deps, current = runtime.context, state["task_current"]
    flags = state["task_flags"]
    emit(
        Agent.WRITER,
        "writer.revise",
        f"Revising §{current.order + 1} {current.title}: {len(flags)} flagged statement(s)…",
        section_id=current.id,
    )
    flagged = "\n".join(f"- {f.sentence}\n  problem ({f.verdict}): {f.problem}" for f in flags)
    result = await deps.llm.parse(
        agent=Agent.WRITER,
        tier=Tier.STRONG,
        instructions=REVISE_INSTRUCTIONS,
        input=(
            f"Section:\n{current.markdown}\n\nFlagged statements:\n{flagged}\n\n"
            f"Findings available to this section:\n" + "\n\n".join(state["task_findings"])
        ),
        schema=SectionDraft,
        name="writer.revise",
    )
    revised = current.model_copy(
        update={"markdown": result.parsed.markdown.strip(), "revision": current.revision + 1}
    )
    return {"sections": [revised], "usage": result.usage}


# ---------------------------------------------------------------------------- final report


async def finalize(state: ResearchState, runtime: Runtime[Deps]) -> dict:
    deps = runtime.context
    sections = sorted(state.get("sections", []), key=lambda s: s.order)
    unresolved = state.get("audit_flags", []) if len(state.get("audit_rounds", [])) > 1 else []
    by_section = {s.id: s.markdown for s in sections}
    for flag in unresolved:  # still flagged after the revision round: mark, don't hide
        if flag.section_id in by_section:
            by_section[flag.section_id] = mark_unit(
                by_section[flag.section_id], flag.sentence, UNRESOLVED_MARK
            )
    bodies = [by_section[s.id] for s in sections]

    emit(Agent.WRITER, "writer.summary", "Writing the executive summary…")
    summary = await deps.llm.parse(
        agent=Agent.WRITER,
        tier=Tier.STRONG,
        instructions=EXEC_INSTRUCTIONS,
        input="\n\n".join(bodies),
        schema=ExecSummary,
        name="writer.exec_summary",
    )
    section_ids = {fid for body in bodies for fid in cited_finding_ids(body)}
    bullets = [
        b.strip().lstrip("-• ").strip()
        for b in summary.parsed.bullets
        if b.strip() and set(cited_finding_ids(b)) <= section_ids  # no facts the body lacks
    ]
    exec_md = "## Executive summary\n\n" + "\n".join(f"- {b}" for b in bullets)
    body = "\n\n".join([exec_md, *bodies])

    finding_to_source = {f.id: f.source_id for f in state.get("findings", [])}
    renumbered = renumber_citations(body, finding_to_source)
    cited_body = CITATION_AFTER_PERIOD.sub(r" \1.", renumbered.markdown)
    problems = lint_citations(cited_body, len(renumbered.references))
    problems += [f"unknown finding id {fid} dropped" for fid in renumbered.unknown_ids]

    sources = {s.id: s for s in state.get("sources", [])}
    report = "\n\n".join(
        [
            f"# {state.get('report_title') or state['prompt']}",
            _byline(state, len(renumbered.references)),
            cited_body,
            methodology(state, unresolved=len(unresolved)),
            references([sources[sid] for sid in renumbered.references if sid in sources]),
        ]
    )
    emit(
        Agent.WRITER,
        "writer.done",
        f"Report assembled: {len(sections)} sections, {len(report.split()):,} words, "
        f"{len(renumbered.references)} cited sources"
        + (f", {len(problems)} citation issue(s)" if problems else ", citations clean"),
        words=len(report.split()),
        references=len(renumbered.references),
    )
    return {
        "report_md": report,
        "citation_problems": problems,
        "usage": summary.usage,
        "stage": Stage.DONE,
    }


def _byline(state: ResearchState, n_cited: int) -> str:
    verdicts = state.get("verdicts", {}).values()
    verified = sum(v.status is VerdictStatus.VERIFIED for v in verdicts)
    return (
        f"*Research briefing · {date.today():%d %B %Y} · {n_cited} cited sources · "
        f"{verified} verified findings · depth: {state.get('depth', 'standard')}*"
    )


def methodology(state: ResearchState, *, unresolved: int) -> str:
    """Generated from run state, not by the model, so every number in it is exact."""
    queries = state.get("sub_queries", [])
    sources = state.get("sources", [])
    verdicts = list(state.get("verdicts", {}).values())
    status = Counter(v.status for v in verdicts)
    caught = Counter(v.caught_by for v in verdicts if v.caught_by)
    rounds = state.get("audit_rounds", [])
    reasons = Counter(
        v.reasons[0].split(":")[0] for v in verdicts if v.status is VerdictStatus.REJECTED
    )
    planned = sum(q.origin == "plan" for q in queries)
    lines = [
        "## Methodology & limitations",
        "",
        f"- **Research questions:** {planned} planned, plus "
        f"{_plural(len(queries) - planned, 'follow-up search', 'follow-up searches')} the Critic "
        f"requested ({_plural(state.get('gap_loops', 0), 'gap loop')}; research stopped because: "
        f"{state.get('stop_reason', 'n/a')}).",
        f"- **Sources read:** {len(sources)} pages, {sum(s.is_primary for s in sources)} of them "
        "on the official sites of the companies covered.",
        f"- **Verification:** {len(verdicts)} extracted findings were checked. Each quote was "
        "matched against its source text, each claim against its quote, and third-party claims "
        "against the other sources.",
        f"  - {status[VerdictStatus.VERIFIED]} verified "
        f"({sum(v.first_party for v in verdicts)} stated by the vendor about itself), "
        f"{status[VerdictStatus.SINGLE_SOURCE]} single-source (attributed in the text), "
        f"{status[VerdictStatus.CONTRADICTED]} contradicted by another source (noted in the "
        "text).",
        f"  - {status[VerdictStatus.REJECTED]} rejected and excluded: {caught['grounding']} "
        f"quotes not found in their source, {caught['entailment']} claims their quote did not "
        f"support, {caught['cross_reference']} failed cross-referencing."
        + (
            " Most common reasons: "
            + "; ".join(f"{r} ({n})" for r, n in reasons.most_common(3))
            + "."
            if reasons
            else ""
        ),
    ]
    if rounds:
        first = rounds[0]
        audit = (
            f"- **Sentence audit:** {first.statements_checked} statements were checked against "
            "the findings they cite"
        )
        if first.flagged == 0:
            audit += "; all were supported."
        else:
            audit += f"; {first.flagged} were flagged and revised."
            audit += (
                f" {unresolved} still flagged after revision are marked †."
                if unresolved
                else " None remained flagged after revision."
            )
        lines.append(audit)
    lines.append(
        "- **Limits:** web sources as retrieved on the date above; vendor pages describe their "
        "own products favourably, and pricing changes often. Treat single-source and contradicted "
        "claims as leads to confirm."
    )
    return "\n".join(lines)


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else plural or singular + 's'}"


def references(sources: Sequence[Source]) -> str:
    lines = ["## References", ""]
    for n, s in enumerate(sources, start=1):
        tag = " · vendor source" if s.is_primary else ""
        lines.append(
            f"{n}. [{s.title}]({s.url}): {s.domain}{tag} · accessed {s.fetched_at:%Y-%m-%d}"
        )
    return "\n".join(lines)
