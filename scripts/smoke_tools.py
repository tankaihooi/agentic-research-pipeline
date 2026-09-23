"""Phase 1 live smoke test: search → fetch/extract → cache → embed → Qdrant → retrieve.

Needs OPENAI_API_KEY and TAVILY_API_KEY in .env. Run twice: the second run should report cache
hits and skip re-embedding.

    uv run python scripts/smoke_tools.py
"""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv
from rich.console import Console

from deep_research.config import get_settings
from deep_research.llm import OpenAILLM
from deep_research.memory.page_cache import PageCache
from deep_research.memory.vector_store import VectorStore
from deep_research.models import Agent, Source, Usage, stable_id, utcnow
from deep_research.tools.fetch import Fetcher
from deep_research.tools.search import TavilySearch
from deep_research.tools.text import clean_page_markdown, count_tokens
from deep_research.tools.urls import domain_of, normalize_url

QUERY = "Stripe Billing usage-based pricing"
QUESTION = "How does Stripe charge for metered usage?"

console = Console()


async def main() -> None:
    load_dotenv()
    settings = get_settings()
    llm = OpenAILLM(settings)
    search = TavilySearch(settings)
    fetcher = Fetcher(settings)
    cache = PageCache(settings.cache_dir / "pages", settings.cache_ttl_days)
    store = VectorStore(settings, llm)
    await store.setup()
    usage = Usage()

    hits = await search.search(QUERY, max_results=4)
    console.print(f"[bold]search[/] {QUERY!r} → {len(hits)} hits")
    for hit in hits:
        url = normalize_url(hit.url)
        source_id = stable_id("S", url)
        cached = cache.get(url)
        if cached:
            text, title, how = cached.text, cached.title, "cache"
        elif hit.raw_content:
            text, title, how = hit.raw_content, hit.title, "tavily"
            cache.put(url, title, text)
        else:
            page = await fetcher.fetch(hit.url)
            if page is None:
                console.print(f"  [red]skip[/] {hit.url}")
                continue
            text, title, how = page.text, page.title, "fetch"
            cache.put(url, title, text)
        raw_tokens = count_tokens(text)
        text = clean_page_markdown(text)  # the cache keeps raw text; cleaning happens on use
        source = Source(
            id=source_id,
            url=url,
            title=title,
            domain=domain_of(url),
            sub_query_id="Q-smoke",
            fetched_at=utcnow(),
            token_count=count_tokens(text),
            text_path="",
            from_cache=how == "cache",
        )
        if how == "cache" and await store.has_source(source_id):
            console.print(
                f"  [cyan]{how:6}[/] {url} ({raw_tokens}→{source.token_count} tok, indexed)"
            )
            continue
        usage += await store.index_source(source, text, agent=Agent.SCRAPER)
        console.print(f"  [green]{how:6}[/] {url} ({raw_tokens}→{source.token_count} tok, new)")

    results, search_usage = await store.search(QUESTION, agent=Agent.CRITIC, limit=3)
    usage += search_usage
    console.print(f"\n[bold]retrieve[/] {QUESTION!r}")
    for r in results:
        preview = r.text[:140].replace("\n", " ")
        console.print(f"  {r.score:.3f}  {r.domain}  {preview}…")
    total = usage.total
    console.print(
        f"\nembedding calls={total.calls} tokens={total.input_tokens} cost=${total.cost_usd:.5f}"
    )
    await fetcher.aclose()
    await store.close()


if __name__ == "__main__":
    asyncio.run(main())
