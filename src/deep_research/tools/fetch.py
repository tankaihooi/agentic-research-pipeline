"""Fallback page fetcher for URLs the search provider could not extract.

Plain httpx + trafilatura (main-content extraction to markdown). It respects robots.txt, caps
response size, skips non-HTML content, and never raises: a failed fetch returns `None` so one bad
page cannot take down a sub-query.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura
from pydantic import BaseModel

from deep_research.config import Settings
from deep_research.observability import tool_span

USER_AGENT = "DeepResearchBot/0.1 (research agent; respects robots.txt)"
MAX_BYTES = 5_000_000
HTML_TYPES = ("text/html", "application/xhtml+xml", "text/plain")


class FetchedPage(BaseModel):
    url: str
    final_url: str
    title: str
    text: str


class Fetcher:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=settings.fetch_timeout_s,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        self._sem = asyncio.Semaphore(settings.fetch_concurrency)
        self._robots: dict[str, RobotFileParser | None] = {}
        self._robots_lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    @tool_span(name="fetch")
    async def fetch(self, url: str) -> FetchedPage | None:
        if not await self._allowed(url):
            return None
        async with self._sem:
            try:
                response = await self._client.get(url)
            except httpx.HTTPError:
                return None
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        if response.status_code >= 400 or (content_type and content_type not in HTML_TYPES):
            return None
        if len(response.content) > MAX_BYTES:
            return None
        return await asyncio.to_thread(_extract, url, str(response.url), response.text)

    async def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        async with self._robots_lock:
            if origin not in self._robots:
                self._robots[origin] = await self._load_robots(origin)
        parser = self._robots[origin]
        return parser is None or parser.can_fetch(USER_AGENT, url)

    async def _load_robots(self, origin: str) -> RobotFileParser | None:
        try:
            response = await self._client.get(f"{origin}/robots.txt", timeout=5.0)
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None  # no robots.txt: everything allowed
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser


def _extract(url: str, final_url: str, html: str) -> FetchedPage | None:
    text = trafilatura.extract(
        html,
        url=final_url,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_comments=False,
        favor_recall=True,
    )
    if not text or len(text) < 200:
        return None
    metadata = trafilatura.extract_metadata(html, default_url=final_url)
    title = (metadata.title if metadata and metadata.title else None) or final_url
    return FetchedPage(url=url, final_url=final_url, title=title, text=text)
