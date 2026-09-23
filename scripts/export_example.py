"""Copy a finished run into examples/<name>/ for the repo.

    uv run python scripts/export_example.py <run_id> <name> [--public-trace URL]

Keeps what a reader or `research replay` / `research show` needs: the report, the event log,
metrics and source list. Private LangSmith links are dropped from run.json; pass
`--public-trace` once a trace has been shared.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from deep_research.config import get_settings
from deep_research.runner import RunInfo

FILES = ("report.md", "events.jsonl", "metrics.json", "sources.json", "sub_queries.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("name")
    parser.add_argument("--public-trace", default=None)
    args = parser.parse_args()

    src = get_settings().runs_dir / args.run_id
    dest = Path("examples") / args.name
    dest.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy(src / name, dest / name)
    info = RunInfo.load(src)
    info.status = "complete"
    info.traces = [args.public_trace] if args.public_trace else []
    info.save(dest)
    print(f"exported {args.run_id} -> {dest}")


if __name__ == "__main__":
    main()
