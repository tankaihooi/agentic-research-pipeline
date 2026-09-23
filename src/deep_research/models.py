"""Domain models shared by every agent.

These are the payloads that move between agents. Page text is deliberately absent: a `Source`
points at text on disk (and in the vector store) and never carries it, so graph state stays small
no matter how much the scraper reads.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


def stable_id(prefix: str, *parts: str, length: int = 8) -> str:
    """Deterministic short id, so re-running or resuming a step produces the same ids."""
    digest = hashlib.sha1("\x1f".join(parts).encode()).hexdigest()[:length]
    return f"{prefix}-{digest}"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Agent(StrEnum):
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    SCRAPER = "scraper"
    CRITIC = "critic"
    WRITER = "writer"
    AUDITOR = "auditor"


class Stage(StrEnum):
    PLANNING = "planning"
    RESEARCHING = "researching"
    VERIFYING = "verifying"
    WRITING = "writing"
    AUDITING = "auditing"
    DONE = "done"


class SubQuery(BaseModel):
    id: str
    question: str
    search_terms: list[str]
    rationale: str
    origin: Literal["plan", "gap"] = "plan"
    avoid_domains: list[str] = Field(default_factory=list)  # gap loops seeking independent sources


class Source(BaseModel):
    id: str
    url: str
    title: str
    domain: str
    sub_query_id: str
    fetched_at: datetime
    is_primary: bool = False
    token_count: int  # after boilerplate cleaning: what agents actually read
    raw_token_count: int = 0  # as returned by search/fetch, for the compression metric
    text_path: str
    from_cache: bool = False


class FindingCategory(StrEnum):
    FEATURE = "feature"
    PRICING = "pricing"
    LAUNCH = "launch"
    INTEGRATION = "integration"
    LIMITATION = "limitation"
    MARKET = "market"
    OTHER = "other"


class Finding(BaseModel):
    """One atomic, checkable claim plus the verbatim quote that supposedly supports it."""

    id: str
    sub_query_id: str
    source_id: str
    claim: str
    quote: str
    entity: str
    category: FindingCategory


class VerdictStatus(StrEnum):
    VERIFIED = "verified"
    SINGLE_SOURCE = "single_source"
    CONTRADICTED = "contradicted"
    REJECTED = "rejected"


CriticCheck = Literal["grounding", "entailment", "cross_reference"]


class Verdict(BaseModel):
    finding_id: str
    status: VerdictStatus
    reasons: list[str] = Field(default_factory=list)
    corroborating_source_ids: list[str] = Field(default_factory=list)
    contradicting_source_ids: list[str] = Field(default_factory=list)
    grounding_score: float | None = None
    first_party: bool = False  # stated by the entity's own site, so authoritative on its own
    caught_by: CriticCheck | None = None  # which check rejected it

    @property
    def usable(self) -> bool:
        return self.status is not VerdictStatus.REJECTED


class OutlineSection(BaseModel):
    id: str
    title: str
    goal: str
    finding_ids: list[str]


class Section(BaseModel):
    id: str
    order: int
    title: str
    markdown: str
    revision: int = 0


class AuditFlag(BaseModel):
    section_id: str
    sentence: str
    cited_finding_ids: list[str]
    verdict: Literal["overstated", "unsupported", "uncited"]
    problem: str


class AuditRound(BaseModel):
    round: int
    sections_checked: int
    statements_checked: int
    flagged: int


class RunError(BaseModel):
    agent: Agent
    where: str
    message: str
    at: datetime = Field(default_factory=utcnow)


class AgentUsage(BaseModel):
    calls: int = 0  # LLM calls
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    embedding_calls: int = 0
    embedding_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0

    def __add__(self, other: AgentUsage) -> AgentUsage:
        return AgentUsage(
            calls=self.calls + other.calls,
            input_tokens=self.input_tokens + other.input_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            embedding_calls=self.embedding_calls + other.embedding_calls,
            embedding_tokens=self.embedding_tokens + other.embedding_tokens,
            latency_ms=self.latency_ms + other.latency_ms,
            cost_usd=self.cost_usd + other.cost_usd,
        )


class Usage(BaseModel):
    """Token, latency and cost accounting, keyed by agent."""

    by_agent: dict[Agent, AgentUsage] = Field(default_factory=dict)

    @classmethod
    def single(cls, agent: Agent, usage: AgentUsage) -> Usage:
        return cls(by_agent={agent: usage})

    def __add__(self, other: Usage) -> Usage:
        merged = dict(self.by_agent)
        for agent, usage in other.by_agent.items():
            merged[agent] = merged[agent] + usage if agent in merged else usage
        return Usage(by_agent=merged)

    @property
    def total(self) -> AgentUsage:
        return sum(self.by_agent.values(), AgentUsage())


class AgentEvent(BaseModel):
    """One line in the live log / events.jsonl. The UI and replay render only these."""

    ts: datetime = Field(default_factory=utcnow)
    agent: Agent
    kind: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
