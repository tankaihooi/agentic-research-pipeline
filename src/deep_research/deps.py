"""Run-scoped dependencies, injected into graph nodes through LangGraph's typed runtime context.

Nodes receive `runtime: Runtime[Deps]` and never construct clients themselves, so tests swap in
fakes and providers (search, vector store) can be replaced without touching agent code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from deep_research.config import Settings
from deep_research.llm import LLMClient, OpenAILLM
from deep_research.memory.page_cache import PageCache
from deep_research.memory.vector_store import VectorStore
from deep_research.tools.fetch import Fetcher
from deep_research.tools.search import SearchProvider, TavilySearch


@dataclass
class Deps:
    settings: Settings
    llm: LLMClient
    search: SearchProvider
    fetcher: Fetcher
    store: VectorStore
    cache: PageCache
    run_dir: Path

    @property
    def sources_dir(self) -> Path:
        return self.run_dir / "sources"

    async def aclose(self) -> None:
        await self.fetcher.aclose()
        await self.store.close()


async def build_deps(settings: Settings, run_dir: Path) -> Deps:
    llm = OpenAILLM(settings)
    store = VectorStore(settings, llm)
    await store.setup()
    (run_dir / "sources").mkdir(parents=True, exist_ok=True)
    return Deps(
        settings=settings,
        llm=llm,
        search=TavilySearch(settings),
        fetcher=Fetcher(settings),
        store=store,
        cache=PageCache(settings.cache_dir / "pages", settings.cache_ttl_days),
        run_dir=run_dir,
    )
