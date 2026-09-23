"""Frozen evaluation fixtures, built from real runs.

A fixture holds a run's sources, findings and live verdicts, plus *evidence windows* rather than
full page copies. For each page it keeps the title area and a window around every quoted
passage, each prefixed with the headings above it. That is everything the Critic's checks read
(quote grounding, context, heading trail, cross-reference chunks), and it keeps the repo free of
wholesale copies of third-party pages.

    evals/fixtures/<name>/
      meta.json        prompt, depth, brief, primary domains, sub-queries, source run id
      sources.json     Source metadata (text_path -> sources/<id>.md)
      findings.json    extracted findings
      verdicts.json    the live Critic's verdicts
      metrics.json     the run's metrics
      sources/*.md     evidence windows
      planted.json     planted fabrications (evals/plants.py)
      labels.json      reference labels (evals/labels.py)
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter
from rapidfuzz import fuzz

from deep_research.config import Settings
from deep_research.events import EventLog
from deep_research.graph.checkpoint import open_checkpointer
from deep_research.graph.workflow import build_graph
from deep_research.models import Finding, Source, SubQuery, Verdict
from deep_research.tools.text import heading_trail

FIXTURES_DIR = Path(__file__).parent / "fixtures"
WINDOW_CHARS = 1500
TITLE_CHARS = 400
SEPARATOR = "\n\n[…]\n\n"


class FixtureMeta(BaseModel):
    name: str
    source_run_id: str
    prompt: str
    depth: str
    brief: str
    primary_domains: list[str]
    sub_queries: list[SubQuery]
    elapsed_s: float | None = None  # run start to first finished report, from events.jsonl


@dataclass
class Fixture:
    name: str
    root: Path
    meta: FixtureMeta
    sources: list[Source]
    findings: list[Finding]
    live_verdicts: dict[str, Verdict]
    metrics: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def sources_by_id(self) -> dict[str, Source]:
        return {s.id: s for s in self.sources}

    def text(self, source_id: str) -> str:
        path = self.root / self.sources_by_id[source_id].text_path
        return path.read_text(encoding="utf-8") if path.exists() else ""


# One character for one character, so match positions still index the original text.
_SAME_LENGTH = str.maketrans("\u2018\u2019\u201c\u201d\u2013\u2014\u00a0", "''\"\"-- ")


def _locate(quote: str, text: str) -> tuple[int, int] | None:
    haystack = text.translate(_SAME_LENGTH).lower()
    needle = quote.translate(_SAME_LENGTH).lower().strip()
    start = haystack.find(needle)
    if start >= 0:
        return start, start + len(needle)
    alignment = fuzz.partial_ratio_alignment(needle, haystack)
    if alignment is None or alignment.score < 60:  # low bar: we only need the right region
        return None
    return alignment.dest_start, alignment.dest_end


def evidence_windows(text: str, quotes: list[str], width: int = WINDOW_CHARS) -> str:
    """Title area plus merged windows around each quote, each prefixed by its heading trail."""
    spans: list[tuple[int, int]] = [(0, min(TITLE_CHARS, len(text)))]
    for quote in quotes:
        if located := _locate(quote, text):
            start, end = located
            spans.append((max(0, start - width), min(len(text), end + width)))
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    pieces = []
    for start, end in merged:
        body = text[start:end].strip()
        trail = heading_trail(body[:200], text) if start > 0 else []
        prefix = "".join(f"{'#' * (i + 1)} {h}\n" for i, h in enumerate(trail))
        pieces.append(prefix + body if prefix and not body.startswith("#") else body)
    return SEPARATOR.join(pieces)


async def freeze(run_id: str, name: str, settings: Settings) -> Path:
    """Copy a finished run into evals/fixtures/<name>/ (evidence windows, not full pages)."""
    run_dir = settings.runs_dir / run_id
    root = FIXTURES_DIR / name
    if root.exists():
        shutil.rmtree(root)
    (root / "sources").mkdir(parents=True)

    async with open_checkpointer(settings.runs_dir / "checkpoints.sqlite") as saver:
        snapshot = await build_graph(saver).aget_state({"configurable": {"thread_id": run_id}})
    state = snapshot.values
    run = json.loads((run_dir / "run.json").read_text())
    events = EventLog.read(run_dir / "events.jsonl")
    done = next((e for e in events if e.kind == "writer.done"), events[-1])
    meta = FixtureMeta(
        elapsed_s=round((done.ts - events[0].ts).total_seconds(), 1),
        name=name,
        source_run_id=run_id,
        prompt=run["prompt"],
        depth=run["depth"],
        brief=state.get("brief", ""),
        primary_domains=state.get("primary_domains", []),
        sub_queries=state.get("sub_queries", []),
    )
    findings: list[Finding] = state.get("findings", [])
    sources: list[Source] = state.get("sources", [])
    for source in sources:
        full = (run_dir / source.text_path).read_text(encoding="utf-8")
        quotes = [f.quote for f in findings if f.source_id == source.id]
        (root / source.text_path).write_text(evidence_windows(full, quotes), encoding="utf-8")

    def dump(filename: str, payload: Any) -> None:
        (root / filename).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    dump("meta.json", meta.model_dump(mode="json"))
    dump("sources.json", [s.model_dump(mode="json") for s in sources])
    dump("findings.json", [f.model_dump(mode="json") for f in findings])
    dump("verdicts.json", [v.model_dump(mode="json") for v in state.get("verdicts", {}).values()])
    shutil.copy(run_dir / "metrics.json", root / "metrics.json")
    return root


def load(name: str) -> Fixture:
    root = FIXTURES_DIR / name
    read = lambda f: json.loads((root / f).read_text())  # noqa: E731
    verdicts = TypeAdapter(list[Verdict]).validate_python(read("verdicts.json"))
    return Fixture(
        name=name,
        root=root,
        meta=FixtureMeta.model_validate(read("meta.json")),
        sources=TypeAdapter(list[Source]).validate_python(read("sources.json")),
        findings=TypeAdapter(list[Finding]).validate_python(read("findings.json")),
        live_verdicts={v.finding_id: v for v in verdicts},
        metrics=read("metrics.json"),
    )


def available() -> list[str]:
    return sorted(p.name for p in FIXTURES_DIR.iterdir() if (p / "meta.json").exists())
