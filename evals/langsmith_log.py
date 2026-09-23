"""Publish eval results as LangSmith datasets and experiments.

The evals compute results locally first (the source of truth is evals/results/). This module
replays those stored outputs through `aevaluate`, so LangSmith gets a side-by-side experiment
comparison (layer ablations for the Critic, critic-on against critic-off for the report) without
paying for the LLM calls twice.
"""

from __future__ import annotations

from typing import Any, cast

from langsmith import Client
from langsmith.evaluation import aevaluate

CRITIC_DATASET = "deep-research/critic-eval"
ABLATION_DATASET = "deep-research/ablation"
LAYER_SETS = {
    "critic-grounding-only": {"grounding"},
    "critic-grounding+entailment": {"grounding", "entailment"},
    "critic-full": {"grounding", "entailment", "cross_reference"},
}


def _recreate(client: Client, name: str, description: str, examples: list[dict[str, Any]]) -> None:
    if client.has_dataset(dataset_name=name):
        client.delete_dataset(dataset_name=name)
    client.create_dataset(name, description=description)
    client.create_examples(dataset_name=name, examples=examples)


async def log_critic(items: list[dict[str, Any]]) -> list[str]:
    client = Client()
    examples = [
        {
            "inputs": {"fixture": i["fixture"], "finding_id": i["finding_id"], "kind": i["kind"]},
            "outputs": {"should_reject": i["kind"] != "genuine" or i["reference"] == "unsupported"},
            "metadata": {"kind": i["kind"]},
        }
        for i in items
    ]
    _recreate(client, CRITIC_DATASET, "Planted fabrications and sampled real findings", examples)
    by_key = {(i["fixture"], i["finding_id"]): i for i in items}

    def correct(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "key": "correct",
            "score": outputs["rejected"] == reference_outputs["should_reject"],
        }

    def plant_recall(outputs: list[dict], reference_outputs: list[dict]) -> dict[str, Any]:
        plants = [
            o for o, r in zip(outputs, reference_outputs, strict=True) if o["kind"] != "genuine"
        ]
        score = sum(o["rejected"] for o in plants) / len(plants) if plants else None
        return {"key": "plant_recall", "score": score}

    def false_rejection_rate(outputs: list[dict], reference_outputs: list[dict]) -> dict[str, Any]:
        good = [
            o
            for o, r in zip(outputs, reference_outputs, strict=True)
            if o["kind"] == "genuine" and not r["should_reject"]
        ]
        score = sum(o["rejected"] for o in good) / len(good) if good else None
        return {"key": "false_rejection_rate", "score": score}

    urls = []
    for prefix, layers in LAYER_SETS.items():

        async def target(inputs: dict[str, Any], layers: set[str] = layers) -> dict[str, Any]:
            item = by_key[(inputs["fixture"], inputs["finding_id"])]
            return {"kind": item["kind"], "rejected": item["caught_by"] in layers}

        result = await aevaluate(
            target,
            data=CRITIC_DATASET,
            evaluators=[correct],
            # langsmith accepts (outputs, reference_outputs) summary evaluators at runtime
            summary_evaluators=cast("list[Any]", [plant_recall, false_rejection_rate]),
            experiment_prefix=prefix,
            metadata={"layers": sorted(layers)},
            max_concurrency=8,
            client=client,
        )
        urls.append(f"{prefix}: {result.experiment_name}")
    return urls


async def log_ablation(results: list[dict[str, Any]]) -> list[str]:
    client = Client()
    fixtures = sorted({r["fixture"] for r in results})
    examples = [{"inputs": {"fixture": f}, "outputs": {}} for f in fixtures]
    _recreate(
        client, ABLATION_DATASET, "Same evidence, written with and without the Critic", examples
    )
    by_key = {(r["fixture"], r["condition"]): r for r in results}

    def contamination(outputs: dict[str, Any]) -> dict[str, Any]:
        return {"key": "planted_findings_cited", "score": outputs["planted_findings_cited"]}

    def unsupported(outputs: dict[str, Any]) -> dict[str, Any]:
        return {"key": "unsupported_rate", "score": outputs["unsupported_rate"]}

    def not_fully_supported(outputs: dict[str, Any]) -> dict[str, Any]:
        return {"key": "not_fully_supported_rate", "score": outputs["not_fully_supported_rate"]}

    urls = []
    for condition in ("critic-off", "critic-on"):

        async def target(inputs: dict[str, Any], condition: str = condition) -> dict[str, Any]:
            r = by_key[(inputs["fixture"], condition)]
            return {
                "planted_findings_cited": r["contamination"]["planted_findings_cited"],
                "unsupported_rate": r["judge"]["unsupported_rate"],
                "not_fully_supported_rate": r["judge"]["not_fully_supported_rate"],
                "report_md": r.get("report_md", ""),
            }

        result = await aevaluate(
            target,
            data=ABLATION_DATASET,
            evaluators=[contamination, unsupported, not_fully_supported],
            experiment_prefix=f"ablation-{condition}",
            client=client,
        )
        urls.append(f"ablation-{condition}: {result.experiment_name}")
    return urls
