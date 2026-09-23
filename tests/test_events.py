from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from deep_research.events import EventLog, capture_events, emit, event_from_stream_chunk
from deep_research.graph.state import ResearchState
from deep_research.models import Agent


def test_emit_outside_graph_goes_to_fallback_sink() -> None:
    with capture_events() as events:
        emit(Agent.PLANNER, "plan.start", "breaking prompt into queries", n=3)
    assert [e.kind for e in events] == ["plan.start"]
    assert events[0].data == {"n": 3}


async def test_emit_inside_graph_streams_as_custom_chunks() -> None:
    async def node(state: ResearchState) -> dict:
        emit(Agent.SCRAPER, "scrape.navigate", "navigating example.com", url="https://example.com")
        return {}

    builder = StateGraph(ResearchState)
    builder.add_node("node", node)
    builder.add_edge(START, "node")
    builder.add_edge("node", END)
    graph = builder.compile()

    events = []
    async for chunk in graph.astream({"prompt": "x"}, stream_mode="custom"):
        if event := event_from_stream_chunk(chunk):
            events.append(event)
    assert len(events) == 1
    assert events[0].agent is Agent.SCRAPER
    assert events[0].data["url"] == "https://example.com"


def test_event_log_round_trip(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "events.jsonl")
    with capture_events() as events:
        emit(Agent.CRITIC, "critic.reject", "rejected F-1: quote not found", finding_id="F-1")
        emit(Agent.WRITER, "writer.section", "drafting §1")
    for event in events:
        log.append(event)
    assert EventLog.read(log.path) == events
