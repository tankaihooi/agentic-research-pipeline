"""LangGraph state for a research run.

A `TypedDict` with reducers is the idiomatic LangGraph state. Parallel `Send` branches return
partial updates that the reducers merge, and entities stay Pydantic for validation at the edges.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Protocol, Required, TypedDict

from deep_research.config import Depth
from deep_research.models import (
    AuditFlag,
    Finding,
    OutlineSection,
    RunError,
    Section,
    Source,
    Stage,
    SubQuery,
    Usage,
    Verdict,
)


class HasId(Protocol):
    @property
    def id(self) -> str: ...


def upsert_by_id[T: HasId](current: Sequence[T] | None, update: Sequence[T] | None) -> list[T]:
    """Merge lists of entities by id: later writes replace earlier ones, order is preserved.

    Makes parallel branches and resumed/retried nodes idempotent, since ids are deterministic.
    """
    merged: dict[str, T] = {item.id: item for item in current or []}
    for item in update or []:
        merged[item.id] = item
    return list(merged.values())


def merge_verdicts(
    current: dict[str, Verdict] | None, update: dict[str, Verdict] | None
) -> dict[str, Verdict]:
    return {**(current or {}), **(update or {})}


def merge_usage(current: Usage | None, update: Usage | None) -> Usage:
    return (current or Usage()) + (update or Usage())


def append(current: list[RunError] | None, update: list[RunError] | None) -> list[RunError]:
    return [*(current or []), *(update or [])]


class ResearchState(TypedDict, total=False):
    run_id: str
    prompt: Required[str]
    depth: Depth
    started_at: float
    deadline: float
    stage: Stage
    brief: str
    primary_domains: list[str]

    sub_queries: Annotated[list[SubQuery], upsert_by_id]
    sources: Annotated[list[Source], upsert_by_id]
    findings: Annotated[list[Finding], upsert_by_id]
    verdicts: Annotated[dict[str, Verdict], merge_verdicts]
    gap_loops: int

    outline: list[OutlineSection]
    sections: Annotated[list[Section], upsert_by_id]
    audit_flags: list[AuditFlag]
    report_md: str

    usage: Annotated[Usage, merge_usage]
    errors: Annotated[list[RunError], append]
