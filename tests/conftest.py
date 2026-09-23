from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never trace to LangSmith or read real keys from the developer's .env."""
    for var in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    for var in ("OPENAI_API_KEY", "TAVILY_API_KEY"):
        monkeypatch.setenv(var, "")
