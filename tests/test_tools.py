from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from qdrant_client import AsyncQdrantClient

from deep_research.config import Settings
from deep_research.memory.page_cache import PageCache
from deep_research.memory.vector_store import VectorStore
from deep_research.models import Agent, Source, stable_id, utcnow
from deep_research.tools.fetch import Fetcher
from deep_research.tools.search import TavilySearch
from deep_research.tools.urls import domain_of, normalize_url, registrable_domain
from tests.fakes import FakeLLM

# ------------------------------------------------------------------ urls


def test_normalize_url_strips_tracking_and_fragments() -> None:
    a = normalize_url("https://WWW.Stripe.com/billing/?utm_source=x&b=2&a=1#pricing")
    b = normalize_url("https://stripe.com/billing?a=1&b=2")
    assert a == b == "https://stripe.com/billing?a=1&b=2"


def test_domains() -> None:
    assert domain_of("https://www.docs.stripe.com/x") == "docs.stripe.com"
    assert registrable_domain("docs.stripe.com") == "stripe.com"
    assert registrable_domain("news.bbc.co.uk") == "bbc.co.uk"


# ------------------------------------------------------------------ page cache


def test_page_cache_round_trip_and_ttl(tmp_path: Path) -> None:
    cache = PageCache(tmp_path, ttl_days=7)
    assert cache.get("https://a.com") is None
    cache.put("https://a.com", "A", "body")
    page = cache.get("https://a.com")
    assert page is not None and page.text == "body"

    expired = PageCache(tmp_path, ttl_days=0)
    stale = page.model_copy(update={"fetched_at": utcnow() - timedelta(days=1)})
    (tmp_path / next(p.name for p in tmp_path.iterdir())).write_text(stale.model_dump_json())
    assert expired.get("https://a.com") is None


# ------------------------------------------------------------------ fetch

ARTICLE = (
    "<html><head><title>Billing launch</title></head><body><article>{}</article></body></html>"
)
BODY = "".join(f"<p>Stripe Billing paragraph {i} about usage-based pricing.</p>" for i in range(20))


def _fetcher(handler: Any) -> Fetcher:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    return Fetcher(Settings(), client=client)


async def test_fetch_extracts_main_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, html=ARTICLE.format(BODY))

    page = await _fetcher(handler).fetch("https://example.com/post")
    assert page is not None
    assert page.title == "Billing launch"
    assert "paragraph 7" in page.text


async def test_fetch_respects_robots_and_content_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        if request.url.path.endswith(".pdf"):
            return httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})
        return httpx.Response(200, html=ARTICLE.format(BODY))

    fetcher = _fetcher(handler)
    assert await fetcher.fetch("https://example.com/private/page") is None
    assert await fetcher.fetch("https://example.com/doc.pdf") is None
    assert await fetcher.fetch("https://example.com/public") is not None


async def test_fetch_never_raises_on_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    assert await _fetcher(handler).fetch("https://down.example.com/") is None


# ------------------------------------------------------------------ search


class _FakeTavily:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    async def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        self.kwargs = kwargs
        return {
            "results": [
                {
                    "url": "https://stripe.com/billing",
                    "title": "Billing",
                    "content": "snip",
                    "score": 0.9,
                    "raw_content": "# Billing\nfull text",
                },
                {
                    "url": "https://x.com/y",
                    "title": None,
                    "content": "",
                    "score": None,
                    "raw_content": None,
                },
            ]
        }

    async def extract(self, urls: list[str], **kwargs: Any) -> dict[str, Any]:
        return {"results": [{"url": u, "raw_content": f"text of {u}"} for u in urls]}


async def test_tavily_search_maps_results() -> None:
    fake = _FakeTavily()
    search = TavilySearch(Settings(), client=fake)  # type: ignore[arg-type]
    hits = await search.search("stripe billing", max_results=5)
    assert fake.kwargs["include_raw_content"] == "markdown"
    assert hits[0].raw_content == "# Billing\nfull text"
    assert hits[1].title == "https://x.com/y" and hits[1].raw_content is None
    assert await search.extract(["https://a.com"]) == {"https://a.com": "text of https://a.com"}


def test_tavily_requires_key() -> None:
    with pytest.raises(RuntimeError):
        TavilySearch(Settings(tavily_api_key=None))


# ------------------------------------------------------------------ vector store


def _source(url: str) -> Source:
    return Source(
        id=stable_id("S", normalize_url(url)),
        url=url,
        title=url,
        domain=domain_of(url),
        sub_query_id="Q1",
        fetched_at=utcnow(),
        token_count=0,
        text_path="",
    )


async def test_vector_store_index_search_and_filters() -> None:
    settings = Settings(embedding_dims=64)
    store = VectorStore(settings, FakeLLM(dims=64), client=AsyncQdrantClient(location=":memory:"))
    await store.setup()

    billing, retries = _source("https://stripe.com/billing"), _source("https://blog.com/retries")
    await store.index_source(
        billing,
        "Usage based pricing with meters.\n\nInvoices finalize hourly.",
        agent=Agent.SCRAPER,
    )
    await store.index_source(
        retries,
        "Smart retries recover failed payments using machine learning.",
        agent=Agent.SCRAPER,
    )
    assert await store.has_source(billing.id)

    hits, usage = await store.search("failed payments retries", agent=Agent.CRITIC, limit=1)
    assert hits[0].source_id == retries.id
    assert usage.by_agent[Agent.CRITIC].embedding_calls == 1

    excluded, _ = await store.search(
        "failed payments retries", agent=Agent.CRITIC, exclude_source_ids=[retries.id]
    )
    assert all(h.source_id != retries.id for h in excluded)

    scoped, _ = await store.search("anything", agent=Agent.CRITIC, source_ids=[billing.id])
    assert {h.source_id for h in scoped} == {billing.id}


async def test_reindexing_a_source_replaces_its_chunks() -> None:
    settings = Settings(embedding_dims=32)
    client = AsyncQdrantClient(location=":memory:")
    store = VectorStore(settings, FakeLLM(dims=32), client=client)
    await store.setup()
    src = _source("https://stripe.com/billing")
    long_text = "\n\n".join(f"Paragraph {i} " + "word " * 150 for i in range(8))
    await store.index_source(src, long_text, agent=Agent.SCRAPER)
    await store.index_source(src, "Short replacement page.", agent=Agent.SCRAPER)
    count = await client.count(store.sources, exact=True)
    assert count.count == 1
