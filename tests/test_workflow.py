# pyright: reportTypedDictNotRequiredAccess=false
# (a missing state key fails these tests with a KeyError, which is the point)
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest
from qdrant_client import AsyncQdrantClient

from deep_research.agents.extractor import ExtractedFinding, Extraction
from deep_research.agents.planner import PlannedQuery, ResearchPlan
from deep_research.config import Depth, Settings
from deep_research.deps import Deps
from deep_research.graph.scraper_graph import ScrapeState, select
from deep_research.memory.page_cache import PageCache
from deep_research.memory.vector_store import VectorStore
from deep_research.models import Agent, AgentEvent, FindingCategory, SubQuery
from deep_research.runner import RunInfo, execute
from deep_research.tools.fetch import Fetcher
from deep_research.tools.search import SearchHit
from tests.fakes import FakeLLM, FakeSearch, SimulatedCrash

TERMS = ["billing features 2026", "competitor billing", "billing pricing"]


def _page(n: int, topic: str) -> str:
    filler = " ".join(f"Detail sentence {i} about {topic} and how teams use it." for i in range(25))
    fact = f"FACT {topic}-{n}: the product ships feature {n} in 2026."
    return f"# {topic} page {n}\n\n{fact}\n\n{filler}"


def _hits(term: str) -> list[SearchHit]:
    domains = ["stripe.com", "chargebee.com", "example-news.com", "youtube.com"]
    return [
        SearchHit(
            url=f"https://www.{d}/{term.replace(' ', '-')}/{i}",
            title=f"{d} {i}",
            snippet="",
            score=1.0 - i / 10,
            raw_content=_page(i, term),
        )
        for i, d in enumerate(domains)
    ]


def _plan(_: str, __: str) -> ResearchPlan:
    return ResearchPlan(
        brief="Compare billing features.",
        primary_entities=["Stripe"],
        primary_domains=["docs.stripe.com"],
        queries=[
            PlannedQuery(question=f"Question about {t}?", search_terms=[t], rationale="r")
            for t in [*TERMS, "an extra query the preset should drop"]
        ],
    )


def _extract(_: str, page_input: str) -> Extraction:
    match = re.search(r"FACT ([^:]+): (.+?\.)", page_input)
    assert match, "fake page must contain a FACT line"
    return Extraction(
        relevant=True,
        findings=[
            ExtractedFinding(
                claim=f"Fact {match.group(1)} holds.",
                quote=match.group(2),
                entity="Stripe",
                category=FindingCategory.FEATURE,
            )
        ],
    )


def _deps(tmp_path: Path, search: FakeSearch, llm: FakeLLM) -> tuple[Settings, Deps]:
    settings = Settings(runs_dir=tmp_path / "runs", cache_dir=tmp_path / "cache", embedding_dims=16)
    run_dir = settings.runs_dir / "test-run"
    (run_dir / "sources").mkdir(parents=True)
    no_network = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    deps = Deps(
        settings=settings,
        llm=llm,
        search=search,
        fetcher=Fetcher(settings, client=no_network),
        store=VectorStore(settings, llm, client=AsyncQdrantClient(location=":memory:")),
        cache=PageCache(settings.cache_dir, ttl_days=7),
        run_dir=run_dir,
    )
    return settings, deps


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM(responses={ResearchPlan: _plan, Extraction: _extract})


async def test_full_research_phase_offline(tmp_path: Path, llm: FakeLLM) -> None:
    search = FakeSearch(results={t: _hits(t) for t in TERMS})
    settings, deps = _deps(tmp_path, search, llm)
    await deps.store.setup()
    events: list[AgentEvent] = []
    info = RunInfo(
        run_id="test-run", prompt="Stripe billing competitive analysis", depth=Depth.QUICK
    )

    state = await execute(settings, info, resume=False, on_event=events.append, deps=deps)

    # planner clamped to the quick preset's 3 questions
    assert [q.id for q in state["sub_queries"]] == ["Q1", "Q2", "Q3"]
    assert state["primary_domains"] == ["stripe.com"]
    # 3 pages per query (youtube skipped), all from distinct URLs
    sources = state["sources"]
    assert len(sources) == 9
    assert not any("youtube" in s.domain for s in sources)
    assert {s.is_primary for s in sources if s.domain == "stripe.com"} == {True}
    assert all(0 < s.token_count <= s.raw_token_count for s in sources)
    # every finding's quote is verbatim from its saved source text
    run_dir = settings.runs_dir / "test-run"
    by_id = {s.id: s for s in sources}
    assert len(state["findings"]) == 9
    for f in state["findings"]:
        assert f.quote in (run_dir / by_id[f.source_id].text_path).read_text()
    # usage is attributed per agent; events narrate every agent that ran
    assert state["usage"].by_agent[Agent.PLANNER].calls == 1
    scraper = state["usage"].by_agent[Agent.SCRAPER]
    assert scraper.calls == 9  # one extraction call per page
    assert scraper.embedding_calls == 9  # one embedding batch per page
    kinds = {e.kind for e in events}
    assert {
        "run.start",
        "plan.query",
        "scrape.navigate",
        "scrape.extract",
        "research.done",
    } <= kinds
    # artefacts
    assert RunInfo.load(run_dir).status == "complete"
    assert len(json.loads((run_dir / "findings.json").read_text())) == 9
    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert metrics["tokens"]["compression_ratio"] > 1
    assert (run_dir / "events.jsonl").read_text().count("\n") == len(events)


async def test_resume_reruns_only_the_unfinished_branch(tmp_path: Path, llm: FakeLLM) -> None:
    search = FakeSearch(results={t: _hits(t) for t in TERMS}, crash_on={TERMS[1]})
    settings, deps = _deps(tmp_path, search, llm)
    await deps.store.setup()
    info = RunInfo(run_id="test-run", prompt="Stripe billing", depth=Depth.QUICK)

    with pytest.raises(SimulatedCrash):
        await execute(settings, info, resume=False, on_event=lambda e: None, deps=deps)
    assert RunInfo.load(settings.runs_dir / "test-run").status == "interrupted"
    planner_calls = len(llm.calls_for(ResearchPlan))

    search.crash_on.clear()
    search.calls.clear()
    state = await execute(settings, info, resume=True, on_event=lambda e: None, deps=deps)

    assert len(llm.calls_for(ResearchPlan)) == planner_calls  # planner not re-run
    assert TERMS[1] in search.calls  # the crashed branch re-ran
    assert len(state["sources"]) == 9
    assert {f.sub_query_id for f in state["findings"]} == {"Q1", "Q2", "Q3"}
    assert len(info.traces) == 2  # one LangSmith root trace per attempt


def test_select_caps_per_host_and_skips_social() -> None:
    hits = (
        [
            SearchHit(url=f"https://docs.stripe.com/{i}", title="", snippet="", score=0.9 - i / 100)
            for i in range(4)
        ]
        + [
            SearchHit(url="https://stripe.com/blog/billing", title="", snippet="", score=0.6),
        ]
        + [
            SearchHit(url="https://www.youtube.com/watch?v=1", title="", snippet="", score=0.99),
            SearchHit(url="https://blog.example.com/a", title="", snippet="", score=0.5),
        ]
    )
    q = SubQuery(id="Q1", question="q", search_terms=["t"], rationale="r")
    chosen = select({"sub_query": q, "hits": hits, "pages_per_query": 5})["hits"]
    urls = [h.url for h in chosen]
    assert urls == [
        "https://docs.stripe.com/0",
        "https://docs.stripe.com/1",
        "https://stripe.com/blog/billing",  # same company, different host: not capped
        "https://blog.example.com/a",
    ]


def test_select_prefers_primary_sources() -> None:
    hits = [
        SearchHit(url="https://listicle.example.com/best-billing", title="", snippet="", score=0.9),
        SearchHit(url="https://docs.stripe.com/billing", title="", snippet="", score=0.75),
    ]
    q = SubQuery(id="Q1", question="q", search_terms=["t"], rationale="r")
    state: ScrapeState = {
        "sub_query": q,
        "hits": hits,
        "pages_per_query": 1,
        "primary_domains": ["stripe.com"],
    }
    assert [h.url for h in select(state)["hits"]] == ["https://docs.stripe.com/billing"]
