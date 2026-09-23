"""LangSmith tracing setup.

LangGraph and `wrap_openai` trace automatically once `LANGSMITH_TRACING=true` and an API key are
present in the environment. This module checks that state, builds the root-run config so every
run is findable by id, and gives tools a consistent `@tool_span` decorator.
"""

from __future__ import annotations

import os
import warnings
from collections.abc import Callable
from typing import Any, TypeVar, cast
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langsmith import traceable
from langsmith.run_trees import get_cached_client

from deep_research.config import Depth, Settings

F = TypeVar("F", bound=Callable[..., Any])
DEFAULT_ENDPOINT = "https://api.smith.langchain.com"


def tool_span(name: str) -> Callable[[F], F]:
    """Trace a tool call (search, fetch) as its own LangSmith span."""
    return cast("Callable[[F], F]", traceable(run_type="tool", name=name))


def retriever_span(name: str) -> Callable[[F], F]:
    """Trace a vector-store query as a LangSmith retriever span."""
    return cast("Callable[[F], F]", traceable(run_type="retriever", name=name))


def tracing_enabled() -> bool:
    flag = os.getenv("LANGSMITH_TRACING", os.getenv("LANGCHAIN_TRACING_V2", "")).lower()
    has_key = bool(os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY"))
    return flag in {"1", "true", "yes"} and has_key


def langsmith_project() -> str:
    return os.getenv("LANGSMITH_PROJECT", "default")


def langsmith_endpoint() -> str:
    return os.getenv("LANGSMITH_ENDPOINT", DEFAULT_ENDPOINT)


def check_langsmith() -> tuple[bool, str]:
    """Make one authenticated API call, so a wrong key or region fails loudly up front.

    Without this, a misconfigured key only shows up as background ingest errors while the run
    itself looks healthy.
    """
    endpoint = langsmith_endpoint()
    try:
        next(iter(get_cached_client().list_projects(limit=1)), None)
    except Exception as exc:
        hint = ""
        if "403" in str(exc):
            hint = (
                " (a 403 usually means the key's region does not match LANGSMITH_ENDPOINT:"
                " US is the default, EU/APAC keys need their regional endpoint)"
            )
        return False, f"{endpoint}: {type(exc).__name__}{hint}"
    return True, endpoint


def flush_traces(timeout_s: float = 10.0) -> None:
    """Block until queued spans are uploaded. Short-lived CLI processes call this before exit."""
    if tracing_enabled():
        get_cached_client().flush(timeout=timeout_s)


def trace_url(root_run_id: UUID) -> str | None:
    """LangSmith URL of a run's root trace, or None if tracing is off or it is not indexed yet."""
    if not tracing_enabled():
        return None
    client = get_cached_client()
    try:
        run = client.read_run(root_run_id)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return client.get_run_url(run=run, project_name=langsmith_project())
    except Exception:
        return None


def run_config(
    run_id: str, root_trace_id: UUID, prompt: str, depth: Depth, settings: Settings, **extra: Any
) -> RunnableConfig:
    """Root config for a graph run.

    `thread_id` keys the checkpoints (so resume finds them). `run_id` fixes the LangSmith root
    trace id, so the CLI can print a link to exactly this run's trace.
    """
    return {
        "run_name": "deep_research",
        "run_id": root_trace_id,
        "configurable": {"thread_id": run_id},
        "tags": ["deep-research", f"depth:{depth.value}"],
        "metadata": {
            "run_id": run_id,
            "prompt": prompt,
            "depth": depth.value,
            "fast_model": settings.fast_model,
            "strong_model": settings.strong_model,
            "embedding_model": settings.embedding_model,
            **extra,
        },
        "recursion_limit": 200,
    }
