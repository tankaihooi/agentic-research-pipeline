"""Scraper subgraph: search → select → read pages → extract findings, for one sub-query.

The parent graph runs one instance per sub-query in parallel via `Send`. Page text only ever
lives on disk (the page cache and `runs/<id>/sources/`) and in Qdrant, never in graph state, so
checkpoints stay small however much gets read.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Required, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from deep_research.agents.extractor import extract_findings
from deep_research.deps import Deps
from deep_research.events import emit
from deep_research.graph.state import append, merge_usage, upsert_by_id
from deep_research.models import (
    Agent,
    Finding,
    RunError,
    Source,
    SubQuery,
    Usage,
    stable_id,
    utcnow,
)
from deep_research.tools.search import SearchHit
from deep_research.tools.text import clean_page_markdown, count_tokens
from deep_research.tools.urls import domain_of, normalize_url, registrable_domain

# Login walls and video/social pages yield little extractable text.
SKIP_DOMAINS = frozenset(
    {
        "youtube.com",
        "youtu.be",
        "tiktok.com",
        "instagram.com",
        "facebook.com",
        "x.com",
        "twitter.com",
        "linkedin.com",
        "pinterest.com",
    }
)
MIN_PAGE_TOKENS = 150
SPARE_RESULTS = 3
MAX_PER_HOST = 2  # per hostname, so docs.stripe.com and stripe.com/blog both get a turn
# Search scores are relevance, not authority. Official vendor pages (docs, pricing, changelogs)
# outrank third-party listicles for a competitive analysis, so they get a ranking boost.
PRIMARY_BOOST = 0.2


class ScrapeState(TypedDict, total=False):
    sub_query: Required[SubQuery]
    brief: str
    primary_domains: list[str]
    pages_per_query: int
    run_started_at: datetime
    hits: list[SearchHit]  # private to the subgraph; raw page content is stripped
    sources: Annotated[list[Source], upsert_by_id]
    findings: Annotated[list[Finding], upsert_by_id]
    usage: Annotated[Usage, merge_usage]
    errors: Annotated[list[RunError], append]


class ScrapeOutput(TypedDict, total=False):
    sources: Annotated[list[Source], upsert_by_id]
    findings: Annotated[list[Finding], upsert_by_id]
    usage: Annotated[Usage, merge_usage]
    errors: Annotated[list[RunError], append]


def short_url(url: str, limit: int = 70) -> str:
    bare = url.split("://", 1)[-1].removeprefix("www.")
    return bare if len(bare) <= limit else bare[: limit - 1] + "…"


async def search(state: ScrapeState, runtime: Runtime[Deps]) -> dict:
    deps, q = runtime.context, state["sub_query"]
    max_results = state.get("pages_per_query", 5) + SPARE_RESULTS

    async def one(term: str) -> list[SearchHit] | RunError:
        emit(Agent.SCRAPER, "scrape.search", f"[{q.id}] searching: “{term}”", sub_query_id=q.id)
        try:
            return await deps.search.search(term, max_results=max_results)
        except Exception as exc:
            return RunError(agent=Agent.SCRAPER, where=f"search:{term}", message=str(exc))

    results = await asyncio.gather(*(one(t) for t in q.search_terms))
    best: dict[str, SearchHit] = {}
    errors: list[RunError] = []
    for result in results:
        if isinstance(result, RunError):
            errors.append(result)
            continue
        for hit in result:
            key = normalize_url(hit.url)  # dedupe/cache key; the original URL is kept for fetching
            if hit.raw_content and deps.cache.get(key) is None:
                deps.cache.put(key, hit.title, hit.raw_content)
            slim = hit.model_copy(update={"raw_content": None})
            if key not in best or slim.score > best[key].score:
                best[key] = slim
    return {"hits": list(best.values()), "errors": errors}


def select(state: ScrapeState) -> dict:
    q = state["sub_query"]
    per_host: dict[str, int] = {}
    chosen: list[SearchHit] = []
    primaries = set(state.get("primary_domains", []))

    def rank(hit: SearchHit) -> float:
        is_primary = registrable_domain(domain_of(hit.url)) in primaries
        return hit.score + (PRIMARY_BOOST if is_primary else 0.0)

    for hit in sorted(state.get("hits", []), key=rank, reverse=True):
        host = domain_of(hit.url)
        if registrable_domain(host) in SKIP_DOMAINS or per_host.get(host, 0) >= MAX_PER_HOST:
            continue
        per_host[host] = per_host.get(host, 0) + 1
        chosen.append(hit)
        if len(chosen) >= state.get("pages_per_query", 5):
            break
    emit(
        Agent.SCRAPER,
        "scrape.select",
        f"[{q.id}] selected {len(chosen)} of {len(state.get('hits', []))} results",
        sub_query_id=q.id,
    )
    return {"hits": chosen}


async def read_pages(state: ScrapeState, runtime: Runtime[Deps]) -> dict:
    deps, q = runtime.context, state["sub_query"]
    primaries = set(state.get("primary_domains", []))
    started = state.get("run_started_at") or utcnow()

    async def one(hit: SearchHit) -> tuple[Source | None, Usage, RunError | None]:
        emit(Agent.SCRAPER, "scrape.navigate", f"[{q.id}] navigating {short_url(hit.url)}")
        key = normalize_url(hit.url)
        try:
            cached = deps.cache.get(key)
            if cached is None:
                page = await deps.fetcher.fetch(hit.url)
                if page is None:
                    extracted = await deps.search.extract([hit.url])
                    if not extracted:
                        emit(Agent.SCRAPER, "scrape.skip", f"[{q.id}] unreadable, skipping")
                        return None, Usage(), None
                    cached = deps.cache.put(key, hit.title, next(iter(extracted.values())))
                else:
                    cached = deps.cache.put(key, page.title, page.text)
            from_cache = cached.fetched_at < started
            text = clean_page_markdown(cached.text)
            tokens = count_tokens(text)
            if tokens < MIN_PAGE_TOKENS:
                emit(Agent.SCRAPER, "scrape.skip", f"[{q.id}] too little content, skipping")
                return None, Usage(), None

            source_id = stable_id("S", key)
            rel_path = f"sources/{source_id}.md"
            (deps.run_dir / rel_path).write_text(text, encoding="utf-8")
            domain = domain_of(hit.url)
            source = Source(
                id=source_id,
                url=hit.url,
                title=cached.title or hit.title,
                domain=domain,
                sub_query_id=q.id,
                fetched_at=cached.fetched_at,
                is_primary=registrable_domain(domain) in primaries,
                token_count=tokens,
                raw_token_count=count_tokens(cached.text),
                text_path=rel_path,
                from_cache=from_cache,
            )
            usage = Usage()
            if not (from_cache and await deps.store.has_source(source_id)):
                usage = await deps.store.index_source(source, text, agent=Agent.SCRAPER)
            emit(
                Agent.SCRAPER,
                "scrape.read",
                f"[{q.id}] read {domain}: {tokens:,} tokens"
                f" (cleaned from {source.raw_token_count:,}){' · cached' if from_cache else ''}",
                source_id=source_id,
                tokens=tokens,
                raw_tokens=source.raw_token_count,
            )
            return source, usage, None
        except Exception as exc:
            error = RunError(agent=Agent.SCRAPER, where=f"read:{hit.url}", message=repr(exc))
            emit(Agent.SCRAPER, "scrape.error", f"[{q.id}] failed {short_url(hit.url)}: {exc}")
            return None, Usage(), error

    results = await asyncio.gather(*(one(h) for h in state.get("hits", [])))
    usage = sum((u for _, u, _ in results), Usage())
    return {
        "sources": [s for s, _, _ in results if s is not None],
        "errors": [e for _, _, e in results if e is not None],
        "usage": usage,
    }


async def extract(state: ScrapeState, runtime: Runtime[Deps]) -> dict:
    deps, q = runtime.context, state["sub_query"]

    async def one(source: Source) -> tuple[list[Finding], Usage, RunError | None]:
        try:
            text = (deps.run_dir / source.text_path).read_text(encoding="utf-8")
            findings, usage = await extract_findings(
                deps.llm, sub_query=q, source=source, text=text, brief=state.get("brief", "")
            )
        except Exception as exc:
            error = RunError(agent=Agent.SCRAPER, where=f"extract:{source.id}", message=repr(exc))
            return [], Usage(), error
        emit(
            Agent.SCRAPER,
            "scrape.extract",
            f"[{q.id}] extracted {len(findings)} findings from {source.domain}",
            source_id=source.id,
            findings=len(findings),
        )
        return findings, usage, None

    mine = [s for s in state.get("sources", []) if s.sub_query_id == q.id]
    results = await asyncio.gather(*(one(s) for s in mine))
    return {
        "findings": [f for fs, _, _ in results for f in fs],
        "usage": sum((u for _, u, _ in results), Usage()),
        "errors": [e for _, _, e in results if e is not None],
    }


def build_scraper_graph() -> CompiledStateGraph[ScrapeState, Deps, ScrapeState, ScrapeOutput]:
    builder = StateGraph(ScrapeState, context_schema=Deps, output_schema=ScrapeOutput)
    builder.add_node("search", search)
    builder.add_node("select", select)
    builder.add_node("read_pages", read_pages)
    builder.add_node("extract", extract)
    builder.add_edge(START, "search")
    builder.add_edge("search", "select")
    builder.add_edge("select", "read_pages")
    builder.add_edge("read_pages", "extract")
    builder.add_edge("extract", END)
    return builder.compile(name="scraper")
