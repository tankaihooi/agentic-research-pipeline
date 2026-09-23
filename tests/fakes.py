"""Offline test doubles for the LLM client."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

from pydantic import BaseModel

from deep_research.config import Tier
from deep_research.llm import EmbedResult, LLMResult
from deep_research.models import Agent, AgentUsage, Usage

Responder = Callable[[str, str], BaseModel] | BaseModel


@dataclass
class FakeCall:
    agent: Agent
    tier: Tier
    schema: type[BaseModel]
    instructions: str
    input: str


@dataclass
class FakeLLM:
    """Returns scripted structured outputs keyed by schema, and deterministic embeddings.

    `responses[Schema]` is either a model instance or `fn(instructions, input) -> instance`.
    """

    responses: dict[type[BaseModel], Responder] = field(default_factory=dict)
    dims: int = 16
    calls: list[FakeCall] = field(default_factory=list)
    tokens_per_call: tuple[int, int] = (100, 20)

    async def parse[T: BaseModel](
        self,
        *,
        agent: Agent,
        tier: Tier,
        instructions: str,
        input: str,
        schema: type[T],
        name: str | None = None,
    ) -> LLMResult[T]:
        self.calls.append(FakeCall(agent, tier, schema, instructions, input))
        responder = self.responses.get(schema)
        if responder is None:
            raise AssertionError(f"FakeLLM has no scripted response for {schema.__name__}")
        parsed = responder if isinstance(responder, BaseModel) else responder(instructions, input)
        tokens_in, tokens_out = self.tokens_per_call
        usage = AgentUsage(calls=1, input_tokens=tokens_in, output_tokens=tokens_out)
        return LLMResult(parsed=cast(T, parsed), usage=Usage.single(agent, usage), model="fake")

    async def embed(self, texts: list[str], *, agent: Agent) -> EmbedResult:
        vectors = [_hash_vector(text, self.dims) for text in texts]
        usage = AgentUsage(embedding_calls=1, embedding_tokens=sum(len(t.split()) for t in texts))
        return EmbedResult(vectors=vectors, usage=Usage.single(agent, usage))

    def calls_for(self, schema: type[BaseModel]) -> list[FakeCall]:
        return [c for c in self.calls if c.schema is schema]


def _hash_vector(text: str, dims: int) -> list[float]:
    """Bag-of-words hashing embedding: similar texts get similar vectors, no network needed."""
    vec = [0.0] * dims
    for word in text.lower().split():
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        vec[h % dims] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def stub(**fields: Any) -> Any:
    """Tiny attribute bag for faking SDK response objects."""
    from types import SimpleNamespace

    return SimpleNamespace(**fields)


@dataclass
class FakeSearch:
    """Scripted search results keyed by query term. `crash_on` raises a hard, non-Exception
    error for that term, which simulates the process dying mid-run."""

    results: dict[str, list[Any]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    crash_on: set[str] = field(default_factory=set)

    async def search(self, query: str, *, max_results: int) -> list[Any]:
        self.calls.append(query)
        if query in self.crash_on:
            raise SimulatedCrash(query)
        return [h.model_copy() for h in self.results.get(query, [])][:max_results]

    async def extract(self, urls: list[str]) -> dict[str, str]:
        return {}


class SimulatedCrash(BaseException):
    """Not an Exception, so per-page error isolation does not swallow it."""
