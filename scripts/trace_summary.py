"""Summarise a run's LangSmith trace as Markdown: timeline, per-node and per-agent tables.

    uv run python scripts/trace_summary.py <run-id-or-folder> --public-url URL

The data comes from the LangSmith API (every span of the run's root trace), so the document
shows what actually executed: the parallel scraper branches and section writers on a Mermaid
Gantt chart, and the tokens and latency attributed to each agent through the tags that every
LLM call carries.
"""

from __future__ import annotations

import argparse
import statistics
import warnings
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langsmith import Client

from deep_research.config import get_settings
from deep_research.runner import RunInfo

AGENTS = ("planner", "scraper", "critic", "writer", "auditor")
STAGE_OF = {
    "planner": "Plan",
    "research": "Research",
    "join_research": "Research",
    "critic_verify": "Verify",
    "critic_assess": "Verify",
    "writer_outline": "Write",
    "write_section": "Write",
    "audit_sections": "Audit",
    "revise_section": "Audit",
    "finalize": "Finalize",
}


def _secs(start: datetime, end: datetime | None) -> float:
    return ((end or start) - start).total_seconds()


def _clock(seconds: int) -> str:
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def _fetch(root_id: str) -> list[Any]:
    client = Client()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return list(client.list_runs(trace_id=root_id))


def summarise(info: RunInfo, runs: list[Any], public_url: str | None) -> str:
    root = next(r for r in runs if r.parent_run_id is None)
    t0 = root.start_time
    children: dict[str, list[Any]] = defaultdict(list)
    for r in runs:
        if r.parent_run_id:
            children[str(r.parent_run_id)].append(r)

    def descendants(run_id: str) -> list[Any]:
        out, stack = [], list(children[run_id])
        while stack:
            r = stack.pop()
            out.append(r)
            stack.extend(children[str(r.id)])
        return out

    llm_runs = [r for r in runs if r.run_type == "llm"]
    nodes = sorted(
        (r for r in children[str(root.id)] if r.name in STAGE_OF), key=lambda r: r.start_time
    )
    total_tokens = sum(r.total_tokens or 0 for r in llm_runs)
    wall = _secs(root.start_time, root.end_time)

    lines = [
        f"# Execution trace: {info.prompt}",
        "",
        f"Run `{info.run_id}` ({info.depth.value}) · {len(runs)} spans · {len(llm_runs)} LLM "
        f"calls · {total_tokens:,} LLM tokens · {wall:.0f}s wall time",
        "",
        f"**Public LangSmith trace:** {public_url}"
        if public_url
        else "_Public LangSmith trace link: not shared yet._",
        "",
        "Generated from the LangSmith API by `scripts/trace_summary.py`, so every number below "
        "is from the recorded trace.",
        "",
        "## Timeline",
        "",
        "Each bar is one LangGraph node execution. Overlapping bars ran concurrently: the "
        "scraper branches (one per research question), the section writers, and the revisions.",
        "",
        "```mermaid",
        "gantt",
        "    dateFormat HH:mm:ss",
        "    axisFormat %M:%S",
    ]
    current, seen = None, Counter[str]()
    for i, n in enumerate(nodes):
        stage = STAGE_OF[n.name]
        if stage != current:
            seen[stage] += 1  # Mermaid merges repeated section names, so number the gap loop
            suffix = " (gap loop)" if seen[stage] == 2 else f" ({seen[stage]})" * (seen[stage] > 2)
            lines.append(f"    section {stage}{suffix}")
            current = stage
        start = int(_secs(t0, n.start_time))
        end = max(int(_secs(t0, n.end_time)), start + 1)
        label = n.name.replace("_", " ")
        lines.append(f"    {label} :n{i}, {_clock(start)}, {_clock(end)}")
    lines += ["```", ""]

    lines += [
        "## Nodes",
        "",
        "| Node | Starts at | Duration | LLM calls | LLM tokens | Tool / retriever spans |",
        "|---|---|---|---|---|---|",
    ]
    for n in nodes:
        desc = descendants(str(n.id))
        llm = [d for d in desc if d.run_type == "llm"]
        tools = [d for d in desc if d.run_type in ("tool", "retriever")]
        started, took = _secs(t0, n.start_time), _secs(n.start_time, n.end_time)
        tokens = sum(d.total_tokens or 0 for d in llm)
        lines.append(
            f"| {n.name} | +{started:.1f}s | {took:.1f}s | {len(llm)} | {tokens:,} | {len(tools)} |"
        )
    lines.append("")

    lines += [
        "## Agents",
        "",
        "Every LLM call is tagged with its agent and model tier (`llm.py`), so LangSmith "
        "attributes tokens and latency per agent.",
        "",
        "| Agent | LLM calls | Prompt tokens | Completion tokens | Median latency | Max latency |",
        "|---|---|---|---|---|---|",
    ]
    for agent in AGENTS:
        calls = [r for r in llm_runs if agent in (r.tags or [])]
        if not calls:
            continue
        latencies = [_secs(r.start_time, r.end_time) for r in calls]
        lines.append(
            f"| {agent} | {len(calls)} | {sum(r.prompt_tokens or 0 for r in calls):,} | "
            f"{sum(r.completion_tokens or 0 for r in calls):,} | "
            f"{statistics.median(latencies):.1f}s | {max(latencies):.1f}s |"
        )
    tools = defaultdict(list)
    for r in runs:
        if r.run_type in ("tool", "retriever", "embedding"):
            tools[r.name].append(_secs(r.start_time, r.end_time))
    lines += [
        "",
        "## Tools",
        "",
        "| Span | Calls | Median latency |",
        "|---|---|---|",
        *(
            f"| {name} | {len(lat)} | {statistics.median(lat):.2f}s |"
            for name, lat in sorted(tools.items())
        ),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    load_dotenv(".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("run", help="run id under runs/, or a folder containing run.json")
    parser.add_argument("--public-url", default=None)
    parser.add_argument("--out", type=Path, default=Path("docs/trace.md"))
    args = parser.parse_args()

    folder = Path(args.run)
    run_dir = folder if (folder / "run.json").exists() else get_settings().runs_dir / args.run
    info = RunInfo.load(run_dir)
    trace = info.traces[-1]
    root_id = trace.rstrip("/").split("/r/")[-1].split("?")[0]
    markdown = summarise(info, _fetch(root_id), args.public_url)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
