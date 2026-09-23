"""Evaluation entry point.

uv run python -m evals.run_all build stripe-billing=<run_id> vector-dbs=<run_id> ...
uv run python -m evals.run_all critic            # planted-fabrication catch rate
uv run python -m evals.run_all ablation          # report with vs without the Critic
uv run python -m evals.run_all report            # evals/results/RESULTS.md from saved results
uv run python -m evals.run_all all --langsmith   # everything, logged as LangSmith experiments
"""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Annotated, Any

import typer
from dotenv import find_dotenv, load_dotenv
from rich.console import Console

from deep_research.config import Settings, get_settings
from deep_research.llm import OpenAILLM
from deep_research.observability import flush_traces
from evals import ablation, critic_eval, fixtures, labels, plants
from evals.langsmith_log import log_ablation, log_critic

RESULTS = Path(__file__).parent / "results"
GENUINE_SAMPLE = 40
app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.callback()
def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))


def _settings() -> Settings:
    return get_settings()


def _write(name: str, payload: Any) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return path


# ---------------------------------------------------------------------------- build


async def _build(name: str, run_id: str, seed: int) -> None:
    settings = _settings()
    await fixtures.freeze(run_id, name, settings)
    fx = fixtures.load(name)
    llm = OpenAILLM(settings)
    planted = await plants.generate(llm, fx, seed=seed)
    plants.save(fx, planted)
    sample = random.Random(seed).sample(fx.findings, min(GENUINE_SAMPLE, len(fx.findings)))
    to_label = sample + [p.finding for p in planted]
    reference = await labels.label(fx, to_label, settings)
    labels.save(fx, [f.id for f in sample], reference)
    valid = sum(
        reference.get(p.finding.id) is not None and reference[p.finding.id].label == "unsupported"
        for p in planted
    )
    genuine_ok = sum(
        reference.get(f.id) is not None and reference[f.id].label == "supported" for f in sample
    )
    console.print(
        f"[green]{name}[/]: {len(fx.sources)} sources, {len(fx.findings)} findings · "
        f"{len(planted)} plants ({valid} confirmed false by the reference judge) · "
        f"{len(sample)} real findings sampled ({genuine_ok} reference-supported)"
    )


@app.command()
def build(
    pairs: Annotated[list[str], typer.Argument(help="name=run_id pairs")],
    seed: int = 7,
) -> None:
    """Freeze runs into fixtures, generate plants, and label a sample (one-off, ~$0.2 each)."""

    async def go() -> None:
        for pair in pairs:
            name, run_id = pair.split("=", 1)
            await _build(name, run_id, seed)

    asyncio.run(go())
    flush_traces()


# ---------------------------------------------------------------------------- critic


async def _critic(names: list[str], repeats: int = 3) -> list[dict[str, Any]]:
    """Run the Critic eval `repeats` times: model judgments vary run to run, so report a range.

    The headline tables use repeat 1; `repeats` in critic.json holds every repeat's summary.
    """
    settings = _settings()
    llm = OpenAILLM(settings)
    runs: list[list[critic_eval.ItemResult]] = []
    per_fixture: dict[str, Any] = {}
    for repeat in range(1, repeats + 1):
        items: list[critic_eval.ItemResult] = []
        for name in names:
            fx = fixtures.load(name)
            label_file = labels.load(fx)
            if label_file is None:
                raise typer.BadParameter(f"{name} has no labels; run `build` first")
            results, usage = await critic_eval.run(fx, plants.load(fx), label_file, llm, settings)
            items += results
            if repeat == 1:
                per_fixture[name] = {
                    **critic_eval.summarize(results),
                    "cost_usd": usage.total.cost_usd,
                }
            console.print(
                f"critic eval · repeat {repeat} · {name}: {len(results)} items, "
                f"${usage.total.cost_usd:.4f}"
            )
        runs.append(items)
    rows = [i.model_dump(mode="json") for i in runs[0]]
    _write(
        "critic.json",
        {
            "overall": critic_eval.summarize(runs[0]),
            "repeats": [critic_eval.summarize(items) for items in runs],
            "per_fixture": per_fixture,
            "items": rows,
        },
    )
    return rows


@app.command()
def critic(
    fixture: Annotated[list[str] | None, typer.Option()] = None,
    repeats: Annotated[int, typer.Option(help="Independent repeats, to report a range.")] = 3,
) -> None:
    """Planted-fabrication catch rate and false rejections on real findings."""
    asyncio.run(_critic(fixture or fixtures.available(), repeats=repeats))
    flush_traces()


# ---------------------------------------------------------------------------- ablation


async def _ablation(names: list[str], resume: bool = False) -> list[dict[str, Any]]:
    """Each finished condition is saved immediately; `resume` skips the ones already saved."""
    settings = _settings()
    llm = OpenAILLM(settings)
    path = RESULTS / "ablation.json"
    saved = json.loads(path.read_text()) if resume and path.exists() else []
    results: list[dict[str, Any]] = list(saved)
    done = {(r["fixture"], r["condition"]) for r in saved}
    for name in names:
        fx = fixtures.load(name)
        label_file = labels.load(fx)
        valid = [
            p
            for p in plants.load(fx)
            if label_file
            and (lab := label_file.labels.get(p.finding.id))
            and lab.label == "unsupported"
        ]
        for condition in ("critic-off", "critic-on"):
            if (name, condition) in done:
                console.print(f"ablation · {name} · {condition}: already saved, skipping")
                continue
            result = await ablation.run_condition(condition, fx, valid, llm, settings)  # type: ignore[arg-type]
            results.append(result)
            _write(
                "ablation.json", [{k: v for k, v in r.items() if k != "report_md"} for r in results]
            )
            c, j = result["contamination"], result["judge"]
            console.print(
                f"ablation · {name} · {condition}: {c['planted_findings_cited']} plants cited, "
                f"{j['unsupported_rate']} unsupported, {j['not_fully_supported_rate']} not fully "
                f"supported ({c['statements']} statements)"
            )
            report_dir = RESULTS / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / f"{name}.{condition}.md").write_text(result["report_md"])
    return results


@app.command("ablation")
def ablation_cmd(
    fixture: Annotated[list[str] | None, typer.Option()] = None,
    resume: Annotated[bool, typer.Option(help="Skip conditions already saved.")] = False,
) -> None:
    """The same evidence written with and without the Critic."""
    asyncio.run(_ablation(fixture or fixtures.available(), resume=resume))
    flush_traces()


# ---------------------------------------------------------------------------- report


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _frac(r: dict[str, Any]) -> str:
    return f"{r['n']}/{r['of']} ({_pct(r['rate'])})"


def _span(rates: list[float]) -> str:
    mean = sum(rates) / len(rates)
    return f"{_pct(mean)} mean (range {_pct(min(rates))}-{_pct(max(rates))})"


def _pooled_row(rows: list[dict[str, Any]], condition: str) -> str:
    rs = [r for r in rows if r["condition"] == condition and "plant_funnel" in r]
    if not rs:
        return ""
    funnel = [sum(r["plant_funnel"][k] for r in rs) for k in rs[0]["plant_funnel"]]
    statements = sum(r["contamination"]["statements"] for r in rs)
    unsupported = sum(r["judge"]["unsupported"] for r in rs)
    partial = sum(r["judge"]["partially_supported"] for r in rs)
    return (
        f"| **all** | **{condition}** | **{' → '.join(map(str, funnel))}** | "
        f"**{_pct(unsupported / statements)}** | "
        f"**{_pct((unsupported + partial) / statements)}** | **{statements}** |"
    )


CAVEATS = """\
## How to read these numbers

- **Plants are synthetic.** Two kinds are string edits (a changed number or date, a swapped
  company name) and two are written by the strong model. Swapping company names works poorly on
  regulatory text, where there are no rival companies: two of the misses are "GPAI" → "EU"
  swaps that are arguably still true.
- **Reference labels are model labels, not human ones.** The strong model at high reasoning
  judged each item against the source; its rationales are in `evals/fixtures/*/labels.json`
  for review. Plants it did not confirm as false are excluded (4 of 120).
- **The ablation judge is the strong model too.** It reads the source text around each cited
  quote, not the findings, so a fabricated finding cannot vouch for itself.
- **Samples are small:** 116 plants, 120 real findings and about 290 statements per condition.
  Read single-digit differences as directional.
- **Where plants are stopped matters.** With the Critic off, the outline happened to pick only
  4 of 116 plants, and every one it picked reached the final report: the sentence auditor
  checks statements against their findings, so it cannot catch a fabricated finding. The Critic
  is the layer that stops them (1 of 116 reached the Writer, 0 were cited).
"""


def _funnel(r: dict[str, Any]) -> str:
    if funnel := r.get("plant_funnel"):
        return " → ".join(str(v) for v in funnel.values())
    return f"{r['plants_reaching_writer']} → ? → ? → {r['contamination']['planted_findings_cited']}"


def render_markdown() -> str:
    lines = ["# Evaluation results", ""]
    critic_path, ablation_path = RESULTS / "critic.json", RESULTS / "ablation.json"
    names = fixtures.available()
    lines += ["Fixtures: " + ", ".join(f"`{n}`" for n in names), ""]

    if critic_path.exists():
        data = json.loads(critic_path.read_text())
        o = data["overall"]
        reps = data.get("repeats", [o])
        caught = [r["plants"]["caught"]["rate"] for r in reps]
        false_rej = [r["genuine"]["false_rejections"]["rate"] for r in reps]
        lines += [
            "## Critic: planted fabrications",
            "",
            f"**Caught {_frac(o['plants']['caught'])} planted fabrications; wrongly rejected "
            f"{_frac(o['genuine']['false_rejections'])} reference-supported real findings.**",
            "",
            f"Across {len(reps)} independent repeats: plants caught {_span(caught)}, "
            f"false rejections {_span(false_rej)}. Tables below are repeat 1.",
            "",
            "| Plant type | Caught |",
            "|---|---|",
            *(f"| {t} | {_frac(r)} |" for t, r in o["plants"]["by_type"].items()),
            "",
            "| Checks enabled | Plants caught |",
            "|---|---|",
            *(
                f"| {k.removeprefix('up_to_').replace('_', '-')} (cumulative) | {_frac(r)} |"
                for k, r in o["plants"]["cumulative_by_layer"].items()
            ),
            "",
            f"Real findings sampled: {o['genuine']['sampled']} · of the ones the reference judge "
            f"called unsupported, the Critic rejected "
            f"{_frac(o['genuine']['reference_unsupported_caught'])} · rejection precision "
            f"{_frac(o['genuine']['rejection_precision'])}.",
            "",
        ]
    if ablation_path.exists():
        rows = json.loads(ablation_path.read_text())
        lines += [
            "## Ablation: the same evidence, with and without the Critic",
            "",
            "Every real finding plus the valid plants go to the Writer. The plant funnel counts "
            "plants that reached the Writer → were picked by the outline → were cited in first "
            "drafts → were still cited after the auditor's revision round.",
            "",
            "| Fixture | Condition | Plant funnel | Unsupported statements | "
            "Not fully supported | Statements |",
            "|---|---|---|---|---|---|",
            *(
                f"| {r['fixture']} | {r['condition']} | {_funnel(r)} | "
                f"{_pct(r['judge']['unsupported_rate'])} | "
                f"{_pct(r['judge']['not_fully_supported_rate'])} | "
                f"{r['contamination']['statements']} |"
                for r in rows
            ),
            *(_pooled_row(rows, condition) for condition in ("critic-off", "critic-on")),
            "",
        ]
    lines += [
        "## Runs: context compression and cost",
        "",
        "| Fixture | Sources | Findings | Raw → clean → distilled → to Writer (tokens) | "
        "Compression | Cost | Time |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in names:
        fx = fixtures.load(name)
        m, elapsed = fx.metrics, fx.meta.elapsed_s or fx.metrics["elapsed_s"]
        t, c = m["tokens"], m["counts"]
        lines.append(
            f"| {name} | {c['sources']} | {c['findings']} | {t['raw_scraped']:,} → "
            f"{t['after_cleaning']:,} → {t['distilled_findings']:,} → "
            f"{t['verified_for_writer']:,} | {t['compression_ratio']}x | "
            f"${m['total']['cost_usd']:.2f} | {elapsed:.0f}s |"
        )
    lines += ["", CAVEATS]
    return "\n".join(lines)


@app.command()
def report() -> None:
    """Write evals/results/RESULTS.md from the saved results."""
    path = RESULTS / "RESULTS.md"
    path.write_text(render_markdown())
    console.print(path.read_text())


@app.command("all")
def run_everything(
    langsmith: Annotated[bool, typer.Option(help="Also log LangSmith experiments.")] = False,
    resume: Annotated[bool, typer.Option(help="Reuse saved critic and ablation results.")] = False,
) -> None:
    """Critic eval, ablation, results table, and optionally LangSmith experiments."""

    async def go() -> None:
        names = fixtures.available()
        critic_path = RESULTS / "critic.json"
        if resume and critic_path.exists():
            items = json.loads(critic_path.read_text())["items"]
        else:
            items = await _critic(names)
        results = await _ablation(names, resume=resume)
        if langsmith:
            for line in await log_critic(items) + await log_ablation(results):
                console.print(f"LangSmith experiment · {line}")

    asyncio.run(go())
    report()
    flush_traces()


if __name__ == "__main__":
    app()
