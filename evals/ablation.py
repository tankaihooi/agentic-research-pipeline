"""Ablation: the same evidence, written up with and without the Critic.

The evidence pool is every real finding in the fixture plus every valid plant, standing in for
extraction errors at a known rate. Two conditions run the real graph from the writing stage
(the checkpoint is seeded as if `critic_assess` had just run, so LangGraph routes into
`writer_outline`):

- critic-off: every finding reaches the Writer, all marked verified. This is a pipeline with
  extraction but no verification.
- critic-on:  the Critic judges the whole pool first, and only usable findings reach the Writer.

The sentence auditor runs in both conditions. It checks sentences against the findings they
cite, so it cannot catch a bad finding. The difference between the conditions is the Critic.

Metrics:
- contamination: planted findings the final report cites. Deterministic, and the headline.
- unsupported statements: an independent judge (strong tier) reads each cited statement next
  to the *source text* around its cited findings' quotes (not the findings themselves) and
  marks it supported, partially supported or unsupported.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from deep_research.agents.critic import verify
from deep_research.config import Depth, Settings, Tier
from deep_research.deps import Deps
from deep_research.graph.checkpoint import checkpoint_serde
from deep_research.graph.state import ResearchState
from deep_research.graph.workflow import build_graph
from deep_research.llm import LLMClient, OpenAILLM
from deep_research.memory.page_cache import PageCache
from deep_research.memory.vector_store import VectorStore
from deep_research.models import (
    Agent,
    Finding,
    Section,
    Stage,
    Usage,
    Verdict,
    VerdictStatus,
)
from deep_research.tools.fetch import Fetcher
from deep_research.tools.search import SearchHit
from deep_research.tools.text import audit_units, cited_finding_ids, quote_context
from evals.critic_eval import build_store
from evals.fixtures import Fixture
from evals.plants import Planted

Condition = Literal["critic-off", "critic-on"]


class _NoSearch:
    """The writing stage never searches; fail loudly if it tries."""

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        raise RuntimeError("search is not available in the ablation")

    async def extract(self, urls: list[str]) -> dict[str, str]:
        raise RuntimeError("extract is not available in the ablation")


async def write_report(
    fixture: Fixture,
    findings: list[Finding],
    verdicts: dict[str, Verdict],
    llm: LLMClient,
    settings: Settings,
    thread: str,
) -> ResearchState:
    """Run the real graph's writing stage over the given evidence."""
    graph = build_graph(InMemorySaver(serde=checkpoint_serde()))
    config: RunnableConfig = {"configurable": {"thread_id": thread}, "recursion_limit": 200}
    query_ids = [q.id for q in fixture.meta.sub_queries]
    now = time.time()
    await graph.aupdate_state(
        config,
        {
            "run_id": thread,
            "prompt": fixture.meta.prompt,
            "depth": Depth(fixture.meta.depth),
            "brief": fixture.meta.brief,
            "primary_domains": fixture.meta.primary_domains,
            "sub_queries": fixture.meta.sub_queries,
            "researched_query_ids": query_ids,
            "sources": fixture.sources,
            "findings": findings,
            "verdicts": verdicts,
            "started_at": now,
            "deadline": now + 3600,
            "gap_loops": 0,
            "stop_reason": "evaluation",
            "stage": Stage.WRITING,
        },
        as_node="critic_assess",
    )
    deps = Deps(
        settings=settings,
        llm=llm,
        search=_NoSearch(),
        fetcher=Fetcher(settings),
        store=VectorStore(settings, llm, client=AsyncQdrantClient(location=":memory:")),
        cache=PageCache(settings.cache_dir / "pages", settings.cache_ttl_days),
        run_dir=fixture.root,
    )
    drafts: dict[str, Section] = {}
    async for chunk in graph.astream(None, config, context=deps, stream_mode="updates"):
        for section in (chunk.get("write_section") or {}).get("sections", []):
            drafts[section.id] = section  # first drafts, before the auditor sees them
    await deps.aclose()
    state: ResearchState = (await graph.aget_state(config)).values  # type: ignore[assignment]
    return {**state, "first_drafts": list(drafts.values())}  # type: ignore[typeddict-unknown-key]


# ---------------------------------------------------------------------------- independent judge


class StatementJudgment(BaseModel):
    index: int
    verdict: Literal["supported", "partially_supported", "unsupported"]
    reason: str


class JudgeBatch(BaseModel):
    judgments: list[StatementJudgment]


JUDGE_INSTRUCTIONS = """\
You are an independent fact-checker. Each numbered statement from a report is followed by the
SOURCE TEXT around the evidence it cites. Using only that source text, judge each statement:

- supported: the source text states everything the statement asserts.
- partially_supported: the gist is there, but a detail (number, date, qualifier, company) is not.
- unsupported: the source text does not say it, or says something different.

Attribution counts: "According to X, ..." is supported if the source text says it. Analysis
phrased as interpretation is supported if it follows directly from the source text.
"""


async def judge_sections(
    sections: list[Section], fixture: Fixture, pool: dict[str, Finding], judge: LLMClient
) -> tuple[list[dict[str, Any]], Usage]:
    sources = fixture.sources_by_id

    def evidence(fid: str) -> str:
        f = pool[fid]
        source = sources[f.source_id]
        context = quote_context(f.quote, fixture.text(f.source_id), window_chars=700)
        return f"    [{source.domain}] {context}"

    async def one(section: Section) -> tuple[list[dict[str, Any]], Usage]:
        units = [(u, ids) for u in audit_units(section.markdown) if (ids := cited_finding_ids(u))]
        units = [(u, [i for i in ids if i in pool]) for u, ids in units]
        units = [(u, ids) for u, ids in units if ids]
        if not units:
            return [], Usage()
        blocks = [
            f"({n}) {u}\n  source text:\n" + "\n".join(evidence(i) for i in dict.fromkeys(ids))
            for n, (u, ids) in enumerate(units, start=1)
        ]
        result = await judge.parse(
            agent=Agent.ORCHESTRATOR,
            tier=Tier.STRONG,
            instructions=JUDGE_INSTRUCTIONS,
            input="\n\n".join(blocks),
            schema=JudgeBatch,
            name="eval.judge_section",
        )
        verdicts = {j.index: j for j in result.parsed.judgments}
        rows = [
            {
                "section": section.title,
                "statement": u,
                "cited": ids,
                "verdict": verdicts[n].verdict if n in verdicts else "unjudged",
                "reason": verdicts[n].reason if n in verdicts else "",
            }
            for n, (u, ids) in enumerate(units, start=1)
        ]
        return rows, result.usage

    results = await asyncio.gather(*(one(s) for s in sections))
    return [r for rows, _ in results for r in rows], sum((u for _, u in results), Usage())


# ---------------------------------------------------------------------------- conditions


async def run_condition(
    condition: Condition,
    fixture: Fixture,
    plants: list[Planted],
    llm: LLMClient,
    settings: Settings,
) -> dict[str, Any]:
    pool = {f.id: f for f in fixture.findings} | {p.finding.id: p.finding for p in plants}
    planted_ids = {p.finding.id for p in plants}
    findings = list(pool.values())
    critic_usage = Usage()
    if condition == "critic-on":
        store = await build_store(fixture, llm, settings)
        verdicts, critic_usage = await verify(llm, store, fixture.root, findings, fixture.sources)
        await store.close()
    else:
        verdicts = {
            f.id: Verdict(finding_id=f.id, status=VerdictStatus.VERIFIED, reasons=["unchecked"])
            for f in findings
        }
    state = await write_report(
        fixture, findings, verdicts, llm, settings, thread=f"{fixture.name}-{condition}"
    )
    sections = sorted(state.get("sections", []), key=lambda s: s.order)
    judge = OpenAILLM(settings.model_copy(update={"strong_reasoning_effort": "medium"}))
    rows, judge_usage = await judge_sections(sections, fixture, pool, judge)

    cited = {fid for s in sections for fid in cited_finding_ids(s.markdown)}
    drafts: list[Section] = state.get("first_drafts", [])  # type: ignore[typeddict-item]
    cited_in_drafts = {fid for s in drafts for fid in cited_finding_ids(s.markdown)}
    outlined = {fid for sec in state.get("outline", []) for fid in sec.finding_ids}
    usable_plants = {fid for fid in planted_ids if verdicts[fid].usable}
    counts = {
        v: sum(r["verdict"] == v for r in rows)
        for v in ("supported", "partially_supported", "unsupported", "unjudged")
    }
    judged = len(rows) - counts["unjudged"]
    return {
        "fixture": fixture.name,
        "condition": condition,
        "pool": {"findings": len(pool), "planted": len(planted_ids)},
        "plants_reaching_writer": len(usable_plants),
        # where plants were stopped: the outline's selection, then the auditor's revision round
        "plant_funnel": {
            "reaching_writer": len(usable_plants),
            "in_outline": len(outlined & planted_ids),
            "cited_in_first_drafts": len(cited_in_drafts & planted_ids),
            "cited_in_final_report": len(cited & planted_ids),
        },
        "contamination": {
            "planted_findings_cited": len(cited & planted_ids),
            "statements_citing_a_plant": sum(bool(set(r["cited"]) & planted_ids) for r in rows),
            "statements": len(rows),
        },
        "judge": {
            **counts,
            "unsupported_rate": round(counts["unsupported"] / judged, 3) if judged else None,
            "not_fully_supported_rate": round(
                (counts["unsupported"] + counts["partially_supported"]) / judged, 3
            )
            if judged
            else None,
        },
        "report": {
            "sections": len(sections),
            "words": len(state.get("report_md", "").split()),
            "findings_cited": len(cited),
        },
        "cost_usd": {
            "critic": round(critic_usage.total.cost_usd, 4),
            "writing": round(state.get("usage", Usage()).total.cost_usd, 4),
            "judge": round(judge_usage.total.cost_usd, 4),
        },
        "statements": rows,
        "report_md": state.get("report_md", ""),
    }
