"""Cross-run page cache on disk: a URL fetched recently is not scraped again.

The vector store holds chunks for semantic retrieval. This cache holds the full cleaned page,
which the extractor and the Critic's grounding check need verbatim.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

from deep_research.models import utcnow


class CachedPage(BaseModel):
    url: str
    title: str
    text: str
    fetched_at: datetime


class PageCache:
    def __init__(self, root: Path, ttl_days: int) -> None:
        self.root = root
        self.ttl = timedelta(days=ttl_days)
        root.mkdir(parents=True, exist_ok=True)

    def _path(self, url: str) -> Path:
        return self.root / f"{hashlib.sha1(url.encode()).hexdigest()}.json"

    def get(self, url: str) -> CachedPage | None:
        path = self._path(url)
        if not path.exists():
            return None
        page = CachedPage.model_validate_json(path.read_text(encoding="utf-8"))
        return page if utcnow() - page.fetched_at <= self.ttl else None

    def put(self, url: str, title: str, text: str) -> CachedPage:
        page = CachedPage(url=url, title=title, text=text, fetched_at=utcnow())
        self._path(url).write_text(page.model_dump_json(), encoding="utf-8")
        return page
