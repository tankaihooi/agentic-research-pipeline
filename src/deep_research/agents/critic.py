"""Critic: decides which findings the Writer may use, and whether research needs another pass.

Checks run cheapest first, and each only sees what survived the one before:

1. Grounding (deterministic): the quote must appear in the saved source text. Catches quotes the
   extractor invented, with no LLM call.
2. Entailment (fast model, batched per source): read in context, does the quote support the
   claim? Catches changed numbers, overreach, and claims pinned on the wrong company.
3. Cross-reference (vector retrieval + fast model): do other sources in this run corroborate or
   contradict it? Facts a vendor states about itself on its own site are accepted as first-party.

Then a coverage check per research question decides whether to send gap queries back to the
Scraper, within the run's loop, time and cost budgets.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from langgraph.runtime import Runtime
from langsmith import traceable
from pydantic import BaseModel, Field

from deep_research.config import PRESETS, Depth, Tier
from deep_research.deps import Deps
from deep_research.events import emit
from deep_research.graph.state import ResearchState
from deep_research.llm import LLMClient
from deep_research.memory.vector_store import ChunkHit, VectorStore
from deep_research.models import (
    Agent,
    CriticCheck,
    Finding,
    Source,
    Stage,
    SubQuery,
    Usage,
    Verdict,
    VerdictStatus,
)
from deep_research.tools.text import heading_trail, quote_context, quote_grounding_score
from deep_research.tools.urls import registrable_domain

GROUNDING_THRESHOLD = 85.0
ENTAIL_BATCH = 10
XREF_BATCH = 6
XREF_CHUNKS = 3
MIN_USABLE_PER_QUERY = 6
MIN_VERIFIED_PER_QUERY = 4
MIN_SITES_PER_QUERY = 2  # evidence from a single site is one-sided, however much of it there is
GAP_TIME_FRACTION = 0.5  # only start a gap loop while at least half the time budget remains
GAP_COST_FRACTION = 0.5  # ...and at least half the cost budget remains


# ---------------------------------------------------------------------------- LLM schemas


class EntailmentJudgment(BaseModel):
    finding_id: str
    verdict: Literal["supported", "partially_supported", "not_supported"]
    reason: str = Field(description="Under 20 words. When rejecting, name the mismatch.")


class EntailmentBatch(BaseModel):
    judgments: list[EntailmentJudgment]


class CrossRefJudgment(BaseModel):
    finding_id: str
    verdict: Literal["corroborated", "contradicted", "no_evidence"]
    source_ids: list[str] = Field(description="Excerpt source ids that corroborate or contradict.")
    reason: str = Field(description="Under 20 words.")


class CrossRefBatch(BaseModel):
    judgments: list[CrossRefJudgment]


class GapQuery(BaseModel):
    for_query_id: str
    question: str
    search_terms: list[str] = Field(description="1-2 new search queries, not repeats.")
    rationale: str


class GapPlan(BaseModel):
    queries: list[GapQuery]


ENTAIL_INSTRUCTIONS = """\
You are the Critic in a research pipeline. For each finding, decide whether its quote, read in the
surrounding page context, supports the claim.

- supported: the context states everything the claim says, with the same entity, numbers, dates,
  plan names and scope.
- partially_supported: the claim goes beyond the quote. It adds or changes a number, date or
  qualifier, or generalises (e.g. "all plans" when the quote is about one plan).
- not_supported: the quote is about something else, names a different company or product than
  the claim, or contradicts the claim.

The page title and section headings apply to all text beneath them: a date heading on a
changelog dates every entry under it, and a vendor's page title says whose product it describes.
Judge only against the given text, never from your own knowledge. Be strict about numbers and
entity names. Return one judgment per finding id.
"""

XREF_INSTRUCTIONS = """\
You cross-check claims against excerpts from OTHER sources gathered in the same research run.

- corroborated: at least one excerpt independently states the same fact (entity and numbers
  agree).
- contradicted: an excerpt states a conflicting fact about the same thing, e.g. a different price
  or date for the same plan. If the conflict looks like old vs new information, still mark
  contradicted and say so in the reason.
- no_evidence: the excerpts do not address the claim.

List the ids of the sources (like S-1a2b3c4d) that corroborate or contradict. Judge only from the
excerpts. Return one judgment per finding id.
"""

GAP_INSTRUCTIONS = """\
You are the Critic in a research pipeline. Some research questions do not yet have enough verified
evidence. For each weak question, propose ONE follow-up question with 1-2 new search terms that
address its stated weakness:
- too few facts: aim at authoritative detail (official docs, pricing pages, changelogs).
- all evidence from one site: aim at independent sources (reviews, analyst or press coverage,
  customer experiences, comparisons) and do not target that site again.
Do not repeat earlier search terms. Use at most one site: operator per term.
"""


# ---------------------------------------------------------------------------- helpers


_FINDING_ID = re.compile(r"F-[0-9a-f]{8}")
_SOURCE_ID = re.compile(r"S-[0-9a-f]{8}")


def _clean_id(raw: str, pattern: re.Pattern[str]) -> str:
    """Models sometimes echo ids with brackets or labels ("[F-1a2b3c4d]"); keep just the id."""
    match = pattern.search(raw)
    return match.group(0) if match else raw.strip()


def _short(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def is_first_party(entity: str, source: Source) -> bool:
    """A vendor describing its own product on its own site ("Stripe Billing" on stripe.com)."""
    if not source.is_primary:
        return False
    label = registrable_domain(source.domain).split(".")[0]
    return len(label) >= 3 and label in re.sub(r"[^a-z0-9]", "", entity.lower())


def load_source_texts(run_dir: Path, sources: Sequence[Source]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for source in sources:
        path = run_dir / source.text_path
        if path.exists():
            texts[source.id] = path.read_text(encoding="utf-8")
    return texts


def _batches[T](items: Sequence[T], size: int) -> list[Sequence[T]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _reject(
    finding: Finding, check: CriticCheck, reason: str, grounding_score: float | None = None
) -> Verdict:
    emit(
        Agent.CRITIC,
        "critic.reject",
        f"✗ rejected {finding.id} ({check}): {reason} · “{_short(finding.claim, 70)}”",
        finding_id=finding.id,
        check=check,
    )
    return Verdict(
        finding_id=finding.id,
        status=VerdictStatus.REJECTED,
        reasons=[reason],
        caught_by=check,
        grounding_score=grounding_score,
    )


# ---------------------------------------------------------------------------- the three checks


@dataclass
class Checked:
    finding: Finding
    grounding_score: float


@traceable(name="critic.grounding")
def ground(
    findings: Sequence[Finding], texts: dict[str, str]
) -> tuple[list[Checked], dict[str, Verdict]]:
    passed: list[Checked] = []
    rejected: dict[str, Verdict] = {}
    for f in findings:
        text = texts.get(f.source_id)
        if text is None:
            rejected[f.id] = _reject(f, "grounding", "source text unavailable")
            continue
        score = quote_grounding_score(f.quote, text)
        if score < GROUNDING_THRESHOLD:
            reason = f"quote not found in source ({score:.0f}% best match)"
            rejected[f.id] = _reject(f, "grounding", reason, grounding_score=score)
        else:
            passed.append(Checked(f, score))
    return passed, rejected


@traceable(name="critic.entailment")
async def entail(
    llm: LLMClient, checked: Sequence[Checked], texts: dict[str, str], sources: dict[str, Source]
) -> tuple[list[Checked], dict[str, Verdict], Usage]:
    by_source: dict[str, list[Checked]] = defaultdict(list)
    for c in checked:
        by_source[c.finding.source_id].append(c)
    batches = [b for group in by_source.values() for b in _batches(group, ENTAIL_BATCH)]

    async def judge(batch: Sequence[Checked]) -> tuple[dict[str, EntailmentJudgment], Usage]:
        blocks = []
        for c in batch:
            f, text = c.finding, texts[c.finding.source_id]
            source = sources[f.source_id]
            section = " > ".join(heading_trail(f.quote, text)) or "(none)"
            blocks.append(
                f"[{f.id}]\nclaim: {f.claim}\nentity: {f.entity}\nquote: {f.quote}\n"
                f"page: {source.title} ({source.domain})\nsection: {section}\n"
                f"context: {quote_context(f.quote, text)}"
            )
        result = await llm.parse(
            agent=Agent.CRITIC,
            tier=Tier.FAST,
            instructions=ENTAIL_INSTRUCTIONS,
            input="\n\n".join(blocks),
            schema=EntailmentBatch,
            name="critic.entail_batch",
        )
        judged = {_clean_id(j.finding_id, _FINDING_ID): j for j in result.parsed.judgments}
        return judged, result.usage

    results = await asyncio.gather(*(judge(b) for b in batches))
    judgments = {fid: j for batch_judgments, _ in results for fid, j in batch_judgments.items()}
    usage = sum((u for _, u in results), Usage())

    supported: list[Checked] = []
    rejected: dict[str, Verdict] = {}
    for c in checked:
        j = judgments.get(c.finding.id)
        if j is None:
            reason = "no entailment judgment returned"
            rejected[c.finding.id] = _reject(c.finding, "entailment", reason)
        elif j.verdict == "supported":
            supported.append(c)
        else:
            label = "overstates its quote" if j.verdict == "partially_supported" else "unsupported"
            reason = f"{label}: {j.reason}"
            rejected[c.finding.id] = _reject(
                c.finding, "entailment", reason, grounding_score=c.grounding_score
            )
    return supported, rejected, usage


@traceable(name="critic.cross_reference")
async def cross_reference(
    llm: LLMClient,
    store: VectorStore,
    checked: Sequence[Checked],
    sources: dict[str, Source],
) -> tuple[dict[str, Verdict], Usage]:
    verdicts: dict[str, Verdict] = {}
    to_check: list[Checked] = []
    for c in checked:
        source = sources[c.finding.source_id]
        if is_first_party(c.finding.entity, source):
            verdicts[c.finding.id] = Verdict(
                finding_id=c.finding.id,
                status=VerdictStatus.VERIFIED,
                reasons=[f"first-party: stated by {c.finding.entity} on {source.domain}"],
                grounding_score=c.grounding_score,
                first_party=True,
            )
        else:
            to_check.append(c)

    usage = Usage()
    if not to_check:
        return verdicts, usage
    run_source_ids = list(sources)
    vectors, embed_usage = await store.embed_queries(
        [c.finding.claim for c in to_check], agent=Agent.CRITIC
    )
    usage += embed_usage
    evidence = await asyncio.gather(
        *(
            store.search_vector(
                vector,
                source_ids=run_source_ids,
                exclude_source_ids=[c.finding.source_id],
                limit=XREF_CHUNKS,
            )
            for c, vector in zip(to_check, vectors, strict=True)
        )
    )
    with_evidence = [(c, hits) for c, hits in zip(to_check, evidence, strict=True) if hits]
    for c, hits in zip(to_check, evidence, strict=True):
        if not hits:
            verdicts[c.finding.id] = _single_source(c, "no other source retrieved")

    async def judge(
        batch: Sequence[tuple[Checked, list[ChunkHit]]],
    ) -> tuple[dict[str, CrossRefJudgment], Usage]:
        blocks = []
        for c, hits in batch:
            excerpts = "\n".join(f"  [{h.source_id}] {_short(h.text, 900)}" for h in hits)
            blocks.append(f"[{c.finding.id}] claim: {c.finding.claim}\nexcerpts:\n{excerpts}")
        result = await llm.parse(
            agent=Agent.CRITIC,
            tier=Tier.FAST,
            instructions=XREF_INSTRUCTIONS,
            input="\n\n".join(blocks),
            schema=CrossRefBatch,
            name="critic.cross_reference_batch",
        )
        judged = {_clean_id(j.finding_id, _FINDING_ID): j for j in result.parsed.judgments}
        return judged, result.usage

    results = await asyncio.gather(*(judge(b) for b in _batches(with_evidence, XREF_BATCH)))
    judgments = {fid: j for batch_judgments, _ in results for fid, j in batch_judgments.items()}
    usage += sum((u for _, u in results), Usage())

    for c, hits in with_evidence:
        j = judgments.get(c.finding.id)
        offered = {h.source_id for h in hits}
        cited = [
            sid
            for raw in (j.source_ids if j else [])
            if (sid := _clean_id(raw, _SOURCE_ID)) in offered
        ]
        if j and j.verdict == "corroborated" and cited:
            verdicts[c.finding.id] = Verdict(
                finding_id=c.finding.id,
                status=VerdictStatus.VERIFIED,
                reasons=[j.reason],
                corroborating_source_ids=cited,
                grounding_score=c.grounding_score,
            )
        elif j and j.verdict == "contradicted" and cited:
            emit(
                Agent.CRITIC,
                "critic.contradict",
                f"⚠ {c.finding.id} contradicted by {', '.join(cited)}: {_short(j.reason, 90)}",
                finding_id=c.finding.id,
            )
            verdicts[c.finding.id] = Verdict(
                finding_id=c.finding.id,
                status=VerdictStatus.CONTRADICTED,
                reasons=[j.reason],
                contradicting_source_ids=cited,
                grounding_score=c.grounding_score,
            )
        else:
            verdicts[c.finding.id] = _single_source(c, j.reason if j else "no judgment returned")
    return verdicts, usage


def _single_source(c: Checked, reason: str) -> Verdict:
    return Verdict(
        finding_id=c.finding.id,
        status=VerdictStatus.SINGLE_SOURCE,
        reasons=[reason],
        grounding_score=c.grounding_score,
    )


async def verify(
    llm: LLMClient,
    store: VectorStore,
    run_dir: Path,
    findings: Sequence[Finding],
    sources: Sequence[Source],
) -> tuple[dict[str, Verdict], Usage]:
    """Run all three checks over `findings`. Usable outside the graph (the eval harness does)."""
    by_id = {s.id: s for s in sources}
    texts = load_source_texts(run_dir, sources)
    emit(
        Agent.CRITIC,
        "critic.start",
        f"Verifying {len(findings)} findings: checking every quote against its source…",
    )
    grounded, verdicts = ground(findings, texts)
    emit(
        Agent.CRITIC,
        "critic.summary",
        f"Grounding: {len(grounded)}/{len(findings)} quotes found in their sources",
        check="grounding",
    )

    emit(
        Agent.CRITIC, "critic.start", f"Entailment: do {len(grounded)} quotes support their claims?"
    )
    supported, rejected, usage = await entail(llm, grounded, texts, by_id)
    verdicts |= rejected
    emit(
        Agent.CRITIC,
        "critic.summary",
        f"Entailment: {len(supported)}/{len(grounded)} claims supported by their quotes",
        check="entailment",
    )

    emit(Agent.CRITIC, "critic.start", f"Cross-referencing {len(supported)} claims across sources…")
    xref, xref_usage = await cross_reference(llm, store, supported, by_id)
    verdicts |= xref
    usage += xref_usage
    counts = _status_counts(xref.values())
    emit(
        Agent.CRITIC,
        "critic.summary",
        f"Cross-reference: {counts[VerdictStatus.VERIFIED]} verified "
        f"({sum(v.first_party for v in xref.values())} first-party), "
        f"{counts[VerdictStatus.CONTRADICTED]} contradicted, "
        f"{counts[VerdictStatus.SINGLE_SOURCE]} single-source",
        check="cross_reference",
    )
    return verdicts, usage


def _status_counts(verdicts: Iterable[Verdict]) -> dict[VerdictStatus, int]:
    counts = dict.fromkeys(VerdictStatus, 0)
    for v in verdicts:
        counts[v.status] += 1
    return counts


# ---------------------------------------------------------------------------- coverage & gaps


def root_query_id(query_id: str) -> str:
    return query_id.split(".", 1)[0]


@dataclass
class Coverage:
    query: SubQuery
    usable: int = 0
    verified: int = 0
    sites: set[str] = field(default_factory=set)

    @property
    def problems(self) -> list[str]:
        problems = []
        if self.verified < MIN_VERIFIED_PER_QUERY:
            problems.append(f"only {self.verified} verified findings")
        if self.usable < MIN_USABLE_PER_QUERY:
            problems.append(f"only {self.usable} usable findings")
        if len(self.sites) == 1:
            problems.append(f"all evidence comes from {next(iter(self.sites))}")
        return problems

    @property
    def weak(self) -> bool:
        return bool(self.problems)


def coverage(
    sub_queries: Sequence[SubQuery],
    findings: Sequence[Finding],
    verdicts: dict[str, Verdict],
    sources: Sequence[Source],
) -> list[Coverage]:
    """Per planned question (gap queries roll up into their root): volume and site diversity."""
    domains = {s.id: registrable_domain(s.domain) for s in sources}
    stats = {q.id: Coverage(q) for q in sub_queries if q.origin == "plan"}
    for f in findings:
        v = verdicts.get(f.id)
        root = stats.get(root_query_id(f.sub_query_id))
        if v is None or root is None or not v.usable:
            continue
        root.usable += 1
        root.verified += v.status is VerdictStatus.VERIFIED
        if f.source_id in domains:
            root.sites.add(domains[f.source_id])
    return list(stats.values())


async def plan_gaps(
    llm: LLMClient,
    weak: Sequence[Coverage],
    all_queries: Sequence[SubQuery],
    findings: Sequence[Finding],
    verdicts: dict[str, Verdict],
    loop: int,
) -> tuple[list[SubQuery], Usage]:
    blocks = []
    for c in weak:
        tried = [
            t for q in all_queries if root_query_id(q.id) == c.query.id for t in q.search_terms
        ]
        have = [
            f.claim
            for f in findings
            if root_query_id(f.sub_query_id) == c.query.id
            and (v := verdicts.get(f.id)) is not None
            and v.usable
        ][:8]
        blocks.append(
            f"[{c.query.id}] {c.query.question}\n"
            f"weakness: {'; '.join(c.problems)}\n"
            f"usable findings: {c.usable}, verified: {c.verified}, sites: {sorted(c.sites)}\n"
            f"search terms already tried: {tried}\n"
            f"what we have: {have or 'nothing usable'}"
        )
    result = await llm.parse(
        agent=Agent.CRITIC,
        tier=Tier.FAST,
        instructions=GAP_INSTRUCTIONS,
        input="\n\n".join(blocks),
        schema=GapPlan,
        name="critic.plan_gaps",
    )
    weak_by_id = {c.query.id: c for c in weak}
    gap_queries: dict[str, SubQuery] = {}
    for g in result.parsed.queries:
        root = g.for_query_id.strip(" []")
        if root in weak_by_id and root not in gap_queries:
            one_sided = len(weak_by_id[root].sites) == 1
            gap_queries[root] = SubQuery(
                id=f"{root}.g{loop}",
                question=g.question,
                search_terms=[t for t in g.search_terms if t.strip()][:2] or [g.question],
                rationale=g.rationale,
                origin="gap",
                avoid_domains=sorted(weak_by_id[root].sites) if one_sided else [],
            )
    return list(gap_queries.values()), result.usage


# ---------------------------------------------------------------------------- graph nodes


async def critic_verify(state: ResearchState, runtime: Runtime[Deps]) -> dict:
    deps = runtime.context
    verdicts = state.get("verdicts", {})
    pending = [f for f in state.get("findings", []) if f.id not in verdicts]
    new_verdicts, usage = await verify(
        deps.llm, deps.store, deps.run_dir, pending, state.get("sources", [])
    )
    return {"verdicts": new_verdicts, "usage": usage, "stage": Stage.VERIFYING}


def budget_stop_reason(state: ResearchState) -> str | None:
    """Why another gap loop is not affordable, or None if it is."""
    preset = PRESETS[state.get("depth", Depth.STANDARD)]
    if state.get("gap_loops", 0) >= preset.max_gap_loops:
        return f"gap-loop limit reached ({preset.max_gap_loops})"
    remaining = state.get("deadline", 0.0) - time.time()
    if remaining < preset.deadline_s * GAP_TIME_FRACTION:
        return f"time budget: {max(remaining, 0):.0f}s left of {preset.deadline_s}s"
    spent = state.get("usage", Usage()).total.cost_usd
    if spent > preset.max_cost_usd * GAP_COST_FRACTION:
        return f"cost budget: ${spent:.2f} spent of ${preset.max_cost_usd:.2f}"
    return None


async def critic_assess(state: ResearchState, runtime: Runtime[Deps]) -> dict:
    deps = runtime.context
    verdicts = state.get("verdicts", {})
    findings = state.get("findings", [])
    stats = coverage(state.get("sub_queries", []), findings, verdicts, state.get("sources", []))
    for c in stats:
        mark = f"needs more evidence ({'; '.join(c.problems)})" if c.weak else "✓"
        emit(
            Agent.CRITIC,
            "critic.coverage",
            f"{c.query.id} coverage: {c.usable} usable, {c.verified} verified, "
            f"{len(c.sites)} site(s) — {mark}",
            sub_query_id=c.query.id,
            usable=c.usable,
            verified=c.verified,
        )
    weak = [c for c in stats if c.weak]
    usable = sum(v.usable for v in verdicts.values())

    reason = "coverage met" if not weak else budget_stop_reason(state)
    if reason is None:
        loop = state.get("gap_loops", 0) + 1
        gap_queries, usage = await plan_gaps(
            deps.llm, weak, state.get("sub_queries", []), findings, verdicts, loop
        )
        if gap_queries:
            for q in gap_queries:
                emit(
                    Agent.CRITIC,
                    "critic.gap",
                    f"↻ requesting more evidence · {q.id}: {q.question}",
                    sub_query_id=q.id,
                )
            return {
                "sub_queries": gap_queries,
                "gap_loops": loop,
                "usage": usage,
                "stage": Stage.RESEARCHING,
            }
        reason = "no useful gap queries proposed"
        return {"usage": usage, **_finish(reason, usable)}
    return _finish(reason, usable)


def _finish(reason: str, usable: int) -> dict:
    emit(
        Agent.CRITIC,
        "critic.done",
        f"Research closed ({reason}) → handing {usable} usable findings to the Writer",
        stop_reason=reason,
    )
    return {"stop_reason": reason, "stage": Stage.WRITING}
