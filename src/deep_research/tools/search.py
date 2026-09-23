"""Web search behind a small provider protocol (Tavily by default)."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

import httpx
from pydantic import BaseModel
from tavily import AsyncTavilyClient
from tavily.errors import TimeoutError as TavilyTimeoutError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from deep_research.config import Settings
from deep_research.observability import tool_span


class SearchHit(BaseModel):
    url: str
    title: str
    snippet: str
    score: float
    raw_content: str | None = None


class SearchProvider(Protocol):
    async def search(self, query: str, *, max_results: int) -> list[SearchHit]: ...

    async def extract(self, urls: list[str]) -> dict[str, str]: ...


_TRANSIENT = (httpx.TransportError, httpx.TimeoutException, TavilyTimeoutError)
_retry = retry(
    retry=retry_if_exception_type(_TRANSIENT),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    reraise=True,
)


class TavilySearch:
    """Tavily search with full-page markdown in the same call (`include_raw_content`)."""

    def __init__(self, settings: Settings, client: AsyncTavilyClient | None = None) -> None:
        if client is None:
            if settings.tavily_api_key is None:
                raise RuntimeError("TAVILY_API_KEY is not set")
            client = AsyncTavilyClient(api_key=settings.tavily_api_key.get_secret_value())
        self._client = client
        self._sem = asyncio.Semaphore(settings.search_concurrency)

    @tool_span(name="tavily.search")
    @_retry
    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        async with self._sem:
            response: dict[str, Any] = await self._client.search(
                query,
                search_depth="advanced",
                max_results=max_results,
                include_raw_content="markdown",
            )
        return [
            SearchHit(
                url=r["url"],
                title=r.get("title") or r["url"],
                snippet=r.get("content") or "",
                score=float(r.get("score") or 0.0),
                raw_content=r.get("raw_content") or None,
            )
            for r in response.get("results", [])
        ]

    @tool_span(name="tavily.extract")
    @_retry
    async def extract(self, urls: list[str]) -> dict[str, str]:
        if not urls:
            return {}
        async with self._sem:
            response: dict[str, Any] = await self._client.extract(urls, format="markdown")
        return {
            r["url"]: r["raw_content"] for r in response.get("results", []) if r.get("raw_content")
        }
