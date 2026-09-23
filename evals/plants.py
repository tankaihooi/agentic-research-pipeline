"""Planted fabrications: known-bad findings mixed into real evidence to measure the Critic.

Four kinds, modelled on how extraction actually goes wrong:

- fabricated_quote  invented claim plus an invented quote that is not on the page.
- unsupported_claim invented claim paired with a real quote from the page (a different fact).
- distorted_number  real quote, but a number or date in the claim is changed.
- wrong_entity      real quote, but the claim credits the fact to a different company.

The last two are deterministic string edits. The first two are written once by the strong model
and stored in the fixture, so every eval run sees the same plants.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel, Field, TypeAdapter

from deep_research.config import Tier
from deep_research.llm import LLMClient
from deep_research.models import Agent, Finding, stable_id
from deep_research.tools.text import quote_grounding_score
from evals.fixtures import Fixture


class PlantType(StrEnum):
    FABRICATED_QUOTE = "fabricated_quote"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    DISTORTED_NUMBER = "distorted_number"
    WRONG_ENTITY = "wrong_entity"


class Planted(BaseModel):
    finding: Finding
    type: PlantType
    derived_from: str
    note: str


# ---------------------------------------------------------------------------- deterministic edits

_NUMBER = re.compile(r"(?<![\w.])(\$?)(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(%|[KkMmBb]\b)?")


def _mutate(number: str) -> str:
    value = float(number.replace(",", ""))
    if re.fullmatch(r"(19|20)\d\d", number):  # a year
        return str(int(value) - 1)
    if "." in number:
        decimals = len(number.split(".")[1])
        return f"{value + 0.2 * max(value, 1):.{decimals}f}"
    changed = int(value * 2) if value >= 2 else int(value) + 2
    return f"{changed:,}" if "," in number else str(changed)


_MONTH_BEFORE = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+$", re.IGNORECASE
)


def distort_number(finding: Finding) -> tuple[str, str] | None:
    """Change the first number in the claim that the quote also states. None if there is none.

    Days of the month move by a week (April 29 -> April 22), so the edit stays plausible.
    """
    quote = finding.quote.lower()
    for match in _NUMBER.finditer(finding.claim):
        number = match.group(2)
        if number not in quote:
            continue
        is_day = number.isdigit() and int(number) <= 31
        if is_day and _MONTH_BEFORE.search(finding.claim[: match.start()]):
            day = int(number)
            mutated = str(day + 7 if day <= 21 else day - 7)
        else:
            mutated = _mutate(number)
        if mutated in quote:
            continue
        claim = finding.claim[: match.start(2)] + mutated + finding.claim[match.end(2) :]
        return claim, f"{number} → {mutated}"
    return None


def _core_name(entity: str) -> str:
    return entity.split()[0].strip(",.") if entity.strip() else ""


def swap_entity(finding: Finding, others: list[str]) -> tuple[str, str, str] | None:
    """Credit the claim to another company that the quote does not mention."""
    core = _core_name(finding.entity)
    if len(core) < 3 or core.lower() not in finding.claim.lower():
        return None
    for other in others:
        other_core = _core_name(other)
        if other_core.lower() in (core.lower(), "") or other_core.lower() in finding.quote.lower():
            continue
        claim = re.sub(re.escape(core), other_core, finding.claim, flags=re.IGNORECASE)
        return claim, other, f"{core} → {other_core}"
    return None


# ---------------------------------------------------------------------------- model-written plants


class FakeFact(BaseModel):
    finding_id: str
    false_claim: str = Field(description="Specific, plausible, and NOT stated on the page.")
    fake_quote: str = Field(description="1-2 sentences in the page's style that would support it.")


class FakeBatch(BaseModel):
    fakes: list[FakeFact]


FAKE_INSTRUCTIONS = """\
You help evaluate a fact-checking system by writing realistic FALSE findings.
For each finding given, write:
- false_claim: a specific, plausible claim about the same company that the page does NOT make:
  an invented feature, price, limit, date or integration. It must be false with respect to the
  page, not a paraphrase of anything on it.
- fake_quote: one or two sentences, in the style of the page, that would support the false claim.
  It must not copy sentences from the page.
Return one entry per finding id.
"""


async def _model_fakes(
    llm: LLMClient, fixture: Fixture, bases: list[Finding]
) -> dict[str, FakeFact]:
    sources = fixture.sources_by_id
    blocks = [
        f"[{f.id}] entity: {f.entity}\npage: {sources[f.source_id].title}\n"
        f"real claim: {f.claim}\nreal quote: {f.quote}"
        for f in bases
    ]
    result = await llm.parse(
        agent=Agent.ORCHESTRATOR,
        tier=Tier.STRONG,
        instructions=FAKE_INSTRUCTIONS,
        input="\n\n".join(blocks),
        schema=FakeBatch,
        name="eval.plant_fakes",
    )
    return {fake.finding_id.strip(" []"): fake for fake in result.parsed.fakes}


def _planted(
    base: Finding, claim: str, quote: str, kind: PlantType, note: str, **extra: str
) -> Planted:
    finding = base.model_copy(
        update={
            "id": stable_id("F", base.source_id, "planted", kind.value, claim),
            "claim": claim,
            "quote": quote,
            **extra,
        }
    )
    return Planted(finding=finding, type=kind, derived_from=base.id, note=note)


async def generate(
    llm: LLMClient, fixture: Fixture, per_type: int = 10, seed: int = 7
) -> list[Planted]:
    rng = random.Random(seed)
    pool = list(fixture.findings)
    rng.shuffle(pool)
    used: set[str] = set()
    plants: list[Planted] = []

    def take(predicate: Callable[[Finding], bool], n: int) -> list[Finding]:
        chosen = [f for f in pool if f.id not in used and predicate(f)][:n]
        used.update(f.id for f in chosen)
        return chosen

    for base in take(lambda f: distort_number(f) is not None, per_type):
        claim, note = distort_number(base)  # type: ignore[misc]
        plants.append(_planted(base, claim, base.quote, PlantType.DISTORTED_NUMBER, note))

    entities = [e for e, _ in Counter(f.entity for f in fixture.findings).most_common(12)]
    for base in take(lambda f: swap_entity(f, entities) is not None, per_type):
        claim, other, note = swap_entity(base, entities)  # type: ignore[misc]
        plants.append(_planted(base, claim, base.quote, PlantType.WRONG_ENTITY, note, entity=other))

    bases = take(lambda f: len(f.quote) > 40, per_type * 2 + 6)  # spares for rejected fakes
    fakes = await _model_fakes(llm, fixture, bases)
    fabricated = unsupported = 0
    for base in bases:
        fake = fakes.get(base.id)
        if fake is None:
            continue
        page = fixture.text(base.source_id)
        if fabricated < per_type and quote_grounding_score(fake.fake_quote, page) < 70:
            plants.append(
                _planted(
                    base,
                    fake.false_claim,
                    fake.fake_quote,
                    PlantType.FABRICATED_QUOTE,
                    "invented claim and quote",
                )
            )
            fabricated += 1
        elif unsupported < per_type:
            plants.append(
                _planted(
                    base,
                    fake.false_claim,
                    base.quote,
                    PlantType.UNSUPPORTED_CLAIM,
                    "invented claim, real quote",
                )
            )
            unsupported += 1
    return plants


def save(fixture: Fixture, plants: list[Planted]) -> None:
    payload = [p.model_dump(mode="json") for p in plants]
    (fixture.root / "planted.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def load(fixture: Fixture) -> list[Planted]:
    path = fixture.root / "planted.json"
    if not path.exists():
        return []
    return TypeAdapter(list[Planted]).validate_json(path.read_text())
