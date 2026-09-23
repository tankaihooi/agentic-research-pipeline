"""Agent events: the narrative stream behind the live terminal UI and `research replay`.

Nodes call `emit(...)`. Inside a graph run, events go through LangGraph's custom stream
(`stream_mode="custom"`). Outside one (unit tests, scripts), they go to an optional fallback sink.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from langgraph.config import get_stream_writer

from deep_research.models import Agent, AgentEvent

EVENT_KEY = "agent_event"

_fallback_sink: ContextVar[Callable[[AgentEvent], None] | None] = ContextVar(
    "fallback_event_sink", default=None
)


def emit(agent: Agent, kind: str, message: str, **data: Any) -> AgentEvent:
    event = AgentEvent(agent=agent, kind=kind, message=message, data=data)
    try:
        writer = get_stream_writer()
    except RuntimeError:
        if sink := _fallback_sink.get():
            sink(event)
        return event
    writer({EVENT_KEY: event.model_dump(mode="json")})
    return event


@contextmanager
def capture_events() -> Iterator[list[AgentEvent]]:
    """Collect events emitted outside a graph run (used by tests and scripts)."""
    captured: list[AgentEvent] = []
    token = _fallback_sink.set(captured.append)
    try:
        yield captured
    finally:
        _fallback_sink.reset(token)


def event_from_stream_chunk(chunk: Any) -> AgentEvent | None:
    """Pull an `AgentEvent` out of a `stream_mode="custom"` chunk, if it is one."""
    if isinstance(chunk, dict) and EVENT_KEY in chunk:
        return AgentEvent.model_validate(chunk[EVENT_KEY])
    return None


class EventLog:
    """Append-only JSONL log of a run's events, used for replay and for the video."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: AgentEvent) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(event.model_dump_json() + "\n")

    @staticmethod
    def read(path: Path) -> list[AgentEvent]:
        lines = path.read_text(encoding="utf-8").splitlines()
        return [AgentEvent.model_validate(json.loads(line)) for line in lines if line.strip()]
