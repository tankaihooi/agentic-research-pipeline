# Deep Research & Briefing System

> 🚧 Work in progress. Demo video, public trace and evaluation results land in the final phase.

A multi-agent research system that turns a broad prompt into a multi-page, cited Markdown briefing.
A **Planner** breaks the prompt down, parallel **Scrapers** read the web, a **Critic** rejects any
claim its source doesn't support, and a **Writer** assembles the report. Orchestration uses
LangGraph, and every agent step is traced in LangSmith.

See [docs/architecture.md](docs/architecture.md) for the design.

## Quickstart

```bash
uv sync
cp .env.example .env        # add OPENAI_API_KEY, TAVILY_API_KEY, LANGSMITH_API_KEY
uv run research doctor      # verifies keys and makes one traced LLM call
```

## Development

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest -q
```
