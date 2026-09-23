"""SQLite checkpointing with an explicit deserialization allowlist.

LangGraph persists state after every step, which is what makes `research resume` possible. The
serializer only revives types we list here: newer LangGraph versions refuse unregistered types, and
an allowlist is the safer default anyway since checkpoints are data read back from disk.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel

from deep_research import config, models
from deep_research.tools import search

# Modules whose Pydantic models / enums appear in graph or subgraph state.
STATE_MODULES = (models, config, search)


def _state_types() -> list[tuple[str, str]]:
    allowed: list[tuple[str, str]] = []
    for module in STATE_MODULES:
        for name, obj in inspect.getmembers(module, inspect.isclass):
            is_state_type = issubclass(obj, BaseModel | Enum)
            if obj.__module__ == module.__name__ and is_state_type:
                allowed.append((module.__name__, name))
    return allowed


def checkpoint_serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=_state_types())


@asynccontextmanager
async def open_checkpointer(path: Path) -> AsyncIterator[AsyncSqliteSaver]:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as conn:
        saver = AsyncSqliteSaver(conn, serde=checkpoint_serde())
        await saver.setup()
        yield saver
