"""Planner: turns one broad request into a handful of specific, searchable research questions."""

from __future__ import annotations

from datetime import date

from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from deep_research.config import PRESETS, Depth, Tier
from deep_research.deps import Deps
from deep_research.events import emit
from deep_research.graph.state import ResearchState
from deep_research.models import Agent, Stage, SubQuery
from deep_research.tools.urls import registrable_domain


class PlannedQuery(BaseModel):
    question: str = Field(description="One specific research question, answerable from the web.")
    search_terms: list[str] = Field(
        description="1-2 concise web search queries (keywords, product names, year if recency "
        "matters)."
    )
    rationale: str = Field(description="Why the report needs this, in one sentence.")


class ResearchPlan(BaseModel):
    brief: str = Field(
        description="2-3 sentences: what the final report must deliver and what it must compare."
    )
    primary_entities: list[str] = Field(description="Companies/products central to the request.")
    primary_domains: list[str] = Field(
        description="Official web domains of the primary entities, e.g. 'stripe.com'."
    )
    queries: list[PlannedQuery]


INSTRUCTIONS = """\
You are the Planner in a multi-agent research system. Today's date is {today}.

Break the user's request into {n} specific, non-overlapping research questions that together cover
what a thorough analyst report needs. Other agents will search the web for each question, extract
quote-backed facts, verify them, and write the report. They only research what you plan.

Guidelines:
- Make each question concrete enough that a web search can answer it (name products, features,
  time frames). Avoid vague questions like "What is the market like?".
- Cover the request from different angles. For a competitive analysis, that means the subject's
  capabilities and pricing, the named or obvious competitors, and how they compare.
- If the request is about something "new" or "recent", aim at the last 12-18 months and include
  the year in search terms.
- Search terms are what you would type into a search engine: short and specific. Where official
  documentation, pricing pages, or changelogs would answer the question, aim one term at them
  (e.g. "stripe billing changelog 2026" or "site:stripe.com billing pricing"). Use at most one
  site: operator per term; several site: operators in one query return junk.
- If one question spans several companies, their official pages cannot all be targeted with two
  terms, so prefer questions that each focus on one or two companies.
- List the official domains of every company the report covers, competitors included, so their
  own pages can be treated as primary sources.
"""


async def plan(state: ResearchState, runtime: Runtime[Deps]) -> dict:
    deps = runtime.context
    preset = PRESETS[state.get("depth", Depth.STANDARD)]
    n = preset.max_sub_queries
    emit(Agent.PLANNER, "plan.start", f"Breaking the request into {n} research questions…")

    result = await deps.llm.parse(
        agent=Agent.PLANNER,
        tier=Tier.STRONG,
        instructions=INSTRUCTIONS.format(today=date.today().isoformat(), n=n),
        input=state["prompt"],
        schema=ResearchPlan,
        name="planner.plan",
    )
    plan_ = result.parsed
    sub_queries = [
        SubQuery(
            id=f"Q{i}",
            question=q.question,
            search_terms=[t for t in q.search_terms if t.strip()][:2] or [q.question],
            rationale=q.rationale,
        )
        for i, q in enumerate(plan_.queries[:n], start=1)
    ]
    if not sub_queries:
        raise ValueError("Planner returned no research questions")

    primary_domains = sorted({registrable_domain(d.lower().strip()) for d in plan_.primary_domains})
    for q in sub_queries:
        emit(Agent.PLANNER, "plan.query", f"{q.id}: {q.question}", sub_query_id=q.id)
    emit(
        Agent.PLANNER,
        "plan.done",
        f"Planned {len(sub_queries)} questions · primary sources: {', '.join(primary_domains)}",
        primary_domains=primary_domains,
    )
    return {
        "sub_queries": sub_queries,
        "brief": plan_.brief,
        "primary_domains": primary_domains,
        "stage": Stage.RESEARCHING,
        "usage": result.usage,
    }
