"""Extraction (the Scraper's map step): one page in, a few quote-backed findings out.

This is where most of the context compression happens. A page of thousands of tokens becomes a
short list of atomic claims, each carrying the verbatim quote the Critic will check it against.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from deep_research.config import Tier
from deep_research.llm import LLMClient
from deep_research.models import (
    Agent,
    Finding,
    FindingCategory,
    Source,
    SubQuery,
    Usage,
    stable_id,
)
from deep_research.tools.text import chunk_text

WINDOW_TOKENS = 6_000
MAX_WINDOWS = 3
MAX_FINDINGS_PER_WINDOW = 8


class ExtractedFinding(BaseModel):
    claim: str = Field(description="One self-contained factual sentence naming the entity.")
    quote: str = Field(description="Exact contiguous span copied from the page that supports it.")
    entity: str = Field(description="Company or product the claim is about.")
    category: FindingCategory


class Extraction(BaseModel):
    relevant: bool
    findings: list[ExtractedFinding]


INSTRUCTIONS = f"""\
You read one web page and extract atomic, checkable facts relevant to a research question.

Rules:
- Each finding is ONE specific fact: a feature, price, plan, date, limit, integration, metric,
  customer, or an explicit comparison. Skip vague marketing claims with nothing checkable.
- `quote` must be copied VERBATIM from the page: one contiguous span of 1-3 sentences (at most
  about 60 words) that directly supports the claim. Do not paraphrase, fix typos, or join
  sentences that are not adjacent. A checker rejects any quote that does not appear in the page.
- `claim` restates the fact as a standalone sentence that names the entity and adds nothing the
  quote does not say. Keep time context ("as of 2026", "announced in March") when the page has it.
- `entity` is the company or product the fact is about, even if it is a competitor.
- Prefer concrete details: numbers, dates, product and plan names.
- Return at most {MAX_FINDINGS_PER_WINDOW} findings, most relevant first. If the page is irrelevant
  or has no concrete facts, set relevant=false and return no findings.
"""


def _windows(text: str) -> list[str]:
    chunks = chunk_text(text, max_tokens=WINDOW_TOKENS, overlap_tokens=200)
    return [c.text for c in chunks[:MAX_WINDOWS]]


async def extract_findings(
    llm: LLMClient, *, sub_query: SubQuery, source: Source, text: str, brief: str
) -> tuple[list[Finding], Usage]:
    windows = _windows(text)

    async def one(i: int, window: str) -> tuple[list[ExtractedFinding], Usage]:
        part = f" (part {i + 1}/{len(windows)})" if len(windows) > 1 else ""
        result = await llm.parse(
            agent=Agent.SCRAPER,
            tier=Tier.FAST,
            instructions=INSTRUCTIONS,
            input=(
                f"Research question: {sub_query.question}\n"
                f"Report brief: {brief}\n"
                f"Page: {source.title} ({source.url}){part}\n"
                f"---\n{window}\n---"
            ),
            schema=Extraction,
            name="scraper.extract",
        )
        found = result.parsed.findings if result.parsed.relevant else []
        return found[:MAX_FINDINGS_PER_WINDOW], result.usage

    results = await asyncio.gather(*(one(i, w) for i, w in enumerate(windows)))
    findings: dict[str, Finding] = {}
    usage = Usage()
    for extracted, window_usage in results:
        usage += window_usage
        for f in extracted:
            if not f.claim.strip() or not f.quote.strip():
                continue
            fid = stable_id("F", source.id, f.claim.strip())
            findings[fid] = Finding(
                id=fid,
                sub_query_id=sub_query.id,
                source_id=source.id,
                claim=f.claim.strip(),
                quote=f.quote.strip(),
                entity=f.entity.strip(),
                category=f.category,
            )
    return list(findings.values()), usage
