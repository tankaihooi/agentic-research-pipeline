from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from deep_research.config import MODEL_PRICING, Settings, Tier
from deep_research.llm import LLMOutputError, OpenAILLM, usage_from_response
from deep_research.models import Agent
from tests.fakes import stub


class Answer(BaseModel):
    text: str


class _FakeResponses:
    def __init__(self, parsed: BaseModel | None) -> None:
        self.parsed = parsed
        self.kwargs: dict[str, Any] = {}

    async def parse(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        usage = stub(
            input_tokens=1_000,
            output_tokens=200,
            input_tokens_details=stub(cached_tokens=400),
        )
        return stub(output_parsed=self.parsed, usage=usage)


def _llm(parsed: BaseModel | None) -> tuple[OpenAILLM, _FakeResponses]:
    responses = _FakeResponses(parsed)
    client = stub(responses=responses, embeddings=None)
    return OpenAILLM(Settings(), client=client), responses  # type: ignore[arg-type]


async def test_parse_routes_tier_to_model_and_accounts_cost() -> None:
    llm, responses = _llm(Answer(text="hi"))
    result = await llm.parse(
        agent=Agent.PLANNER, tier=Tier.STRONG, instructions="sys", input="q", schema=Answer
    )
    assert result.parsed.text == "hi"
    assert responses.kwargs["model"] == "gpt-6-sol"
    assert responses.kwargs["text_format"] is Answer
    assert responses.kwargs["langsmith_extra"]["tags"] == ["planner", "strong"]

    usage = result.usage.by_agent[Agent.PLANNER]
    expected = MODEL_PRICING["gpt-6-sol"].cost(1_000, 200, cached_input_tokens=400)
    assert usage.cached_input_tokens == 400
    assert usage.cost_usd == pytest.approx(expected)


async def test_parse_raises_on_refusal() -> None:
    llm, _ = _llm(None)
    with pytest.raises(LLMOutputError):
        await llm.parse(
            agent=Agent.CRITIC, tier=Tier.FAST, instructions="s", input="q", schema=Answer
        )


def test_cached_tokens_are_discounted() -> None:
    price = MODEL_PRICING["gpt-6-luna"]
    assert price.cost(1_000_000, 0, cached_input_tokens=1_000_000) == pytest.approx(0.01)
    assert price.cost(1_000_000, 1_000_000) == pytest.approx(0.60)


def test_embedding_usage_uses_prompt_tokens() -> None:
    usage = usage_from_response("text-embedding-3-small", stub(prompt_tokens=500_000), 5.0)
    assert usage.input_tokens == 500_000
    assert usage.cost_usd == pytest.approx(0.01)
