"""Runtime settings, depth presets, and model pricing.

Everything tunable lives here so a run's behaviour is reproducible from (settings, depth, prompt).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Depth(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class Tier(StrEnum):
    """Model tier. FAST handles high-volume calls, STRONG handles planning and writing."""

    FAST = "fast"
    STRONG = "strong"


class DepthPreset(BaseModel, frozen=True):
    max_sub_queries: int
    pages_per_query: int
    max_gap_loops: int
    deadline_s: int
    max_cost_usd: float


PRESETS: dict[Depth, DepthPreset] = {
    Depth.QUICK: DepthPreset(
        max_sub_queries=3, pages_per_query=3, max_gap_loops=0, deadline_s=240, max_cost_usd=0.50
    ),
    Depth.STANDARD: DepthPreset(
        max_sub_queries=5, pages_per_query=5, max_gap_loops=1, deadline_s=600, max_cost_usd=1.50
    ),
    Depth.DEEP: DepthPreset(
        max_sub_queries=5, pages_per_query=8, max_gap_loops=2, deadline_s=900, max_cost_usd=3.00
    ),
}


class ModelPrice(BaseModel, frozen=True):
    """USD per 1M tokens. Cached input is billed at a discount (10% of input on OpenAI)."""

    input: float
    output: float
    cached_input_ratio: float = 0.1

    def cost(self, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float:
        uncached = max(input_tokens - cached_input_tokens, 0)
        return (
            uncached * self.input
            + cached_input_tokens * self.input * self.cached_input_ratio
            + output_tokens * self.output
        ) / 1_000_000


# Source: developers.openai.com/api/docs/models and /pricing (checked 2026-09-23).
MODEL_PRICING: dict[str, ModelPrice] = {
    "gpt-6-luna": ModelPrice(input=0.10, output=0.50),
    "gpt-6-sol": ModelPrice(input=2.00, output=10.00),
    "gpt-6-astra": ModelPrice(input=10.00, output=50.00),
    "text-embedding-3-small": ModelPrice(input=0.02, output=0.0),
    "text-embedding-3-large": ModelPrice(input=0.13, output=0.0),
}


def price_for(model: str) -> ModelPrice | None:
    return MODEL_PRICING.get(model)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None

    fast_model: str = "gpt-6-luna"
    strong_model: str = "gpt-6-sol"
    fast_reasoning_effort: str = "low"
    strong_reasoning_effort: str = "medium"
    embedding_model: str = "text-embedding-3-small"
    embedding_dims: int = 1536

    runs_dir: Path = Path("runs")
    qdrant_path: Path = Path(".qdrant")
    cache_dir: Path = Path(".cache")
    qdrant_url: str | None = None
    cache_ttl_days: int = 7

    search_concurrency: int = 3
    fetch_concurrency: int = 8
    llm_concurrency: int = 6
    llm_timeout_s: float = 120.0
    llm_max_retries: int = 4
    fetch_timeout_s: float = 20.0

    def model_for(self, tier: Tier) -> str:
        return self.fast_model if tier is Tier.FAST else self.strong_model

    def reasoning_for(self, tier: Tier) -> str:
        return self.fast_reasoning_effort if tier is Tier.FAST else self.strong_reasoning_effort


@lru_cache
def get_settings() -> Settings:
    return Settings()
