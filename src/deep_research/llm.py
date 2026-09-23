"""Thin, traced wrapper over the OpenAI SDK.

Every call is attributed to an agent so per-agent tokens, latency and cost show up both in
LangSmith and in the run's own `metrics.json`. Agents depend on the `LLMClient` protocol, so
tests inject a fake and never touch the network.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import AsyncOpenAI
from pydantic import BaseModel

from deep_research.config import Settings, Tier, price_for
from deep_research.models import Agent, AgentUsage, Usage


class LLMOutputError(RuntimeError):
    """The model refused or returned output that did not match the schema."""


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    parsed: T
    usage: Usage
    model: str


@dataclass(frozen=True)
class EmbedResult:
    vectors: list[list[float]]
    usage: Usage


class LLMClient(Protocol):
    async def parse[T: BaseModel](
        self,
        *,
        agent: Agent,
        tier: Tier,
        instructions: str,
        input: str,
        schema: type[T],
        name: str | None = None,
    ) -> LLMResult[T]: ...

    async def embed(self, texts: list[str], *, agent: Agent) -> EmbedResult: ...


def usage_from_response(model: str, raw_usage: Any, latency_ms: float) -> AgentUsage:
    """Convert an OpenAI Responses/Embeddings usage object into our accounting model."""
    if raw_usage is None:
        return AgentUsage(calls=1, latency_ms=latency_ms)
    input_tokens = getattr(raw_usage, "input_tokens", None)
    if input_tokens is None:  # embeddings report prompt_tokens instead
        input_tokens = getattr(raw_usage, "prompt_tokens", 0)
    output_tokens = getattr(raw_usage, "output_tokens", 0) or 0
    details = getattr(raw_usage, "input_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
    price = price_for(model)
    cost = price.cost(input_tokens, output_tokens, cached) if price else 0.0
    return AgentUsage(
        calls=1,
        input_tokens=input_tokens,
        cached_input_tokens=cached,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=cost,
    )


class OpenAILLM:
    """`LLMClient` backed by the OpenAI Responses API with structured outputs."""

    EMBED_BATCH = 256

    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        self.settings = settings
        if client is None:
            api_key = (
                settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
            )
            client = wrap_openai(
                AsyncOpenAI(
                    api_key=api_key,
                    timeout=settings.llm_timeout_s,
                    max_retries=settings.llm_max_retries,  # SDK backs off on 408/409/429/5xx
                )
            )
        self._client = client
        self._sem = asyncio.Semaphore(settings.llm_concurrency)

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
        model = self.settings.model_for(tier)
        async with self._sem:
            start = time.perf_counter()
            response = await self._client.responses.parse(
                model=model,
                instructions=instructions,
                input=input,
                text_format=schema,
                reasoning={"effort": self.settings.reasoning_for(tier)},  # type: ignore[arg-type]
                store=False,
                langsmith_extra={  # type: ignore[call-arg]
                    "name": name or f"{agent.value}.{schema.__name__}",
                    "tags": [agent.value, tier.value],
                    "metadata": {"agent": agent.value, "tier": tier.value},
                },
            )
            latency_ms = (time.perf_counter() - start) * 1000
        parsed = response.output_parsed
        if parsed is None:
            raise LLMOutputError(f"{agent.value}: no parsed output for {schema.__name__}")
        usage = usage_from_response(model, response.usage, latency_ms)
        return LLMResult(parsed=parsed, usage=Usage.single(agent, usage), model=model)

    @traceable(run_type="embedding", name="embed")
    async def embed(self, texts: list[str], *, agent: Agent) -> EmbedResult:
        model = self.settings.embedding_model
        vectors: list[list[float]] = []
        total = Usage()
        for i in range(0, len(texts), self.EMBED_BATCH):
            batch = texts[i : i + self.EMBED_BATCH]
            async with self._sem:
                start = time.perf_counter()
                response = await self._client.embeddings.create(
                    model=model, input=batch, dimensions=self.settings.embedding_dims
                )
                latency_ms = (time.perf_counter() - start) * 1000
            vectors.extend(item.embedding for item in response.data)
            raw = usage_from_response(model, response.usage, latency_ms)
            usage = AgentUsage(
                embedding_calls=1,
                embedding_tokens=raw.input_tokens,
                latency_ms=raw.latency_ms,
                cost_usd=raw.cost_usd,
            )
            total += Usage.single(agent, usage)
        return EmbedResult(vectors=vectors, usage=total)
