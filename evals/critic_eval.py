"""Critic eval: does it reject planted fabrications, and does it spare genuine findings?

The Critic runs exactly as in production (`agents.critic.verify`) over a mix of sampled real
findings and valid plants, with cross-referencing against a vector store built from the
fixture's evidence windows. Because the checks run in order, each rejection is attributed to the
first check that caught it, which also gives layer ablations for free: "grounding only" catches
exactly what grounding caught, and so on.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from deep_research.agents.critic import verify
from deep_research.config import Settings
from deep_research.llm import LLMClient
from deep_research.memory.vector_store import VectorStore
from deep_research.models import Agent, Usage, VerdictStatus
from evals.fixtures import Fixture
from evals.labels import LabelFile
from evals.plants import Planted, PlantType

LAYERS = ("grounding", "entailment", "cross_reference")


class ItemResult(BaseModel):
    fixture: str
    finding_id: str
    kind: str  # "genuine" or a PlantType value
    reference: str  # "supported" | "unsupported"
    status: VerdictStatus
    caught_by: str | None
    reason: str

    @property
    def rejected(self) -> bool:
        return self.status is VerdictStatus.REJECTED


async def build_store(fixture: Fixture, llm: LLMClient, settings: Settings) -> VectorStore:
    store = VectorStore(settings, llm, client=AsyncQdrantClient(location=":memory:"))
    await store.setup()
    for source in fixture.sources:
        await store.index_source(source, fixture.text(source.id), agent=Agent.CRITIC)
    return store


async def run(
    fixture: Fixture,
    plants: list[Planted],
    labels: LabelFile,
    llm: LLMClient,
    settings: Settings,
) -> tuple[list[ItemResult], Usage]:
    by_id = {f.id: f for f in fixture.findings}
    genuine = [by_id[fid] for fid in labels.genuine_sample if fid in labels.labels]
    valid_plants = [
        p
        for p in plants
        if (lab := labels.labels.get(p.finding.id)) is not None and lab.label == "unsupported"
    ]
    store = await build_store(fixture, llm, settings)
    findings = genuine + [p.finding for p in valid_plants]
    verdicts, usage = await verify(llm, store, fixture.root, findings, fixture.sources)
    await store.close()

    kinds = {f.id: "genuine" for f in genuine} | {p.finding.id: p.type.value for p in valid_plants}
    return [
        ItemResult(
            fixture=fixture.name,
            finding_id=f.id,
            kind=kinds[f.id],
            reference=labels.labels[f.id].label,
            status=verdicts[f.id].status,
            caught_by=verdicts[f.id].caught_by,
            reason=verdicts[f.id].reasons[0] if verdicts[f.id].reasons else "",
        )
        for f in findings
    ], usage


def _rate(n: int, d: int) -> dict[str, Any]:
    return {"n": n, "of": d, "rate": round(n / d, 3) if d else None}


def summarize(items: list[ItemResult]) -> dict[str, Any]:
    plants = [i for i in items if i.kind != "genuine"]
    genuine = [i for i in items if i.kind == "genuine"]
    supported = [i for i in genuine if i.reference == "supported"]
    unsupported_real = [i for i in genuine if i.reference == "unsupported"]
    rejected_real = [i for i in genuine if i.rejected]

    by_type = {
        t.value: _rate(
            sum(i.rejected for i in plants if i.kind == t.value),
            sum(i.kind == t.value for i in plants),
        )
        for t in PlantType
    }
    caught_by = Counter(i.caught_by for i in plants if i.rejected)
    cumulative: dict[str, Any] = {}
    running = 0
    for layer in LAYERS:
        running += caught_by.get(layer, 0)
        cumulative[f"up_to_{layer}"] = _rate(running, len(plants))
    flagged_not_rejected = Counter(
        i.status.value for i in plants if not i.rejected
    )  # a missed plant may still be hedged as single-source or contradicted
    return {
        "plants": {
            "caught": _rate(sum(i.rejected for i in plants), len(plants)),
            "by_type": by_type,
            "caught_by_layer": dict(caught_by),
            "cumulative_by_layer": cumulative,
            "missed_but_hedged": dict(flagged_not_rejected),
        },
        "genuine": {
            "sampled": len(genuine),
            "reference_supported": len(supported),
            "false_rejections": _rate(sum(i.rejected for i in supported), len(supported)),
            "reference_unsupported_caught": _rate(
                sum(i.rejected for i in unsupported_real), len(unsupported_real)
            ),
            "rejection_precision": _rate(
                sum(i.reference == "unsupported" for i in rejected_real), len(rejected_real)
            ),
        },
    }
