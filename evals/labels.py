"""Reference labels: is each finding really supported by its source?

Labels come from the strong model with high reasoning effort, judging each claim against the
source window around its quote. That is a different model and setting from the Critic (fast tier,
low effort). They are silver labels, not human ones: they are stored in `labels.json` with a
rationale per item so they can be reviewed and overridden by hand.

Every plant is labelled too, as a validity check: a plant the reference judge calls supported is
not a fabrication after all, and is dropped from the catch-rate denominator.
"""

from __future__ import annotations

import asyncio
import json
from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter

from deep_research.config import Settings, Tier
from deep_research.llm import OpenAILLM
from deep_research.models import Agent, Finding
from deep_research.tools.text import heading_trail, quote_context
from evals.fixtures import Fixture

BATCH = 8


class Label(BaseModel):
    finding_id: str
    label: Literal["supported", "unsupported"]
    rationale: str


class LabelBatch(BaseModel):
    labels: list[Label]


INSTRUCTIONS = """\
You are the reference annotator for a fact-checking benchmark. For each finding, read the source
excerpt carefully and decide whether the SOURCE supports the CLAIM.

- supported: the source states what the claim says, with the same entity, numbers, dates,
  qualifiers and scope. Headings and the page title apply to the text beneath them.
- unsupported: anything else. The claim adds, changes or generalises a detail, names the wrong
  company or product, or the quoted text does not appear in the source.

Judge only from the excerpt, not from your own knowledge. Give a one-sentence rationale.
"""


def _block(f: Finding, fixture: Fixture) -> str:
    text = fixture.text(f.source_id)
    source = fixture.sources_by_id[f.source_id]
    trail = " > ".join(heading_trail(f.quote, text)) or "(none)"
    return (
        f"[{f.id}]\nclaim: {f.claim}\nentity: {f.entity}\nquoted text: {f.quote}\n"
        f"page: {source.title} ({source.domain})\nsection: {trail}\n"
        f"source excerpt: {quote_context(f.quote, text, window_chars=900)}"
    )


async def label(fixture: Fixture, findings: list[Finding], settings: Settings) -> dict[str, Label]:
    judge = OpenAILLM(settings.model_copy(update={"strong_reasoning_effort": "high"}))

    async def one(batch: list[Finding]) -> list[Label]:
        result = await judge.parse(
            agent=Agent.ORCHESTRATOR,
            tier=Tier.STRONG,
            instructions=INSTRUCTIONS,
            input="\n\n".join(_block(f, fixture) for f in batch),
            schema=LabelBatch,
            name="eval.reference_label",
        )
        return result.parsed.labels

    batches = [findings[i : i + BATCH] for i in range(0, len(findings), BATCH)]
    results = await asyncio.gather(*(one(b) for b in batches))
    ids = {f.id for f in findings}
    labels = {}
    for item in (label for batch in results for label in batch):
        fid = item.finding_id.strip(" []")
        if fid in ids:
            labels[fid] = item.model_copy(update={"finding_id": fid})
    return labels


class LabelFile(BaseModel):
    genuine_sample: list[str] = Field(description="ids of the real findings sampled for the eval")
    labels: dict[str, Label]


def save(fixture: Fixture, sample: list[str], labels: dict[str, Label]) -> None:
    payload = LabelFile(genuine_sample=sample, labels=labels).model_dump(mode="json")
    (fixture.root / "labels.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def load(fixture: Fixture) -> LabelFile | None:
    path = fixture.root / "labels.json"
    return TypeAdapter(LabelFile).validate_json(path.read_text()) if path.exists() else None
