"""Long-term semantic memory in Qdrant.

Chunks are keyed by `(source_id, chunk_index)` and source ids come from the normalised URL, so the
same page indexed by two runs is stored once. The Critic filters retrieval by the current run's
source ids, which lets cached pages from earlier runs take part without being re-embedded.
"""

from __future__ import annotations

import re
import uuid

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models

from deep_research.config import Settings
from deep_research.llm import LLMClient
from deep_research.models import Agent, Source, Usage
from deep_research.observability import retriever_span
from deep_research.tools.text import chunk_text


class ChunkHit(BaseModel):
    source_id: str
    url: str
    domain: str
    chunk_index: int
    text: str
    score: float


def _collection_name(prefix: str, model: str, dims: int) -> str:
    # Encode the embedding space in the name: switching models never mixes vector spaces.
    return f"{prefix}__{re.sub(r'[^a-z0-9]+', '_', model.lower())}__{dims}"


class VectorStore:
    def __init__(
        self, settings: Settings, llm: LLMClient, client: AsyncQdrantClient | None = None
    ) -> None:
        if client is None:
            if settings.qdrant_url:
                client = AsyncQdrantClient(url=settings.qdrant_url)
            else:
                settings.qdrant_path.mkdir(parents=True, exist_ok=True)
                client = AsyncQdrantClient(path=str(settings.qdrant_path))
        self._client = client
        self._llm = llm
        self._dims = settings.embedding_dims
        self.sources = _collection_name("sources", settings.embedding_model, self._dims)
        self._remote = settings.qdrant_url is not None

    async def setup(self) -> None:
        if await self._client.collection_exists(self.sources):
            return
        await self._client.create_collection(
            self.sources,
            vectors_config=models.VectorParams(size=self._dims, distance=models.Distance.COSINE),
        )
        if self._remote:  # payload indexes are a server feature; embedded mode scans
            for field in ("source_id", "domain"):
                await self._client.create_payload_index(
                    self.sources, field, field_schema=models.PayloadSchemaType.KEYWORD
                )

    async def close(self) -> None:
        await self._client.close()

    async def has_source(self, source_id: str) -> bool:
        result = await self._client.count(
            self.sources, count_filter=_match("source_id", source_id), exact=True
        )
        return result.count > 0

    async def index_source(self, source: Source, text: str, *, agent: Agent) -> Usage:
        """Chunk, embed and upsert one page, replacing any previous version of it."""
        chunks = chunk_text(text)
        if not chunks:
            return Usage()
        embedded = await self._llm.embed([c.text for c in chunks], agent=agent)
        await self._client.delete(
            self.sources,
            points_selector=models.FilterSelector(filter=_match("source_id", source.id)),
        )
        await self._client.upsert(
            self.sources,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source.id}:{chunk.index}")),
                    vector=vector,
                    payload={
                        "source_id": source.id,
                        "url": source.url,
                        "domain": source.domain,
                        "title": source.title,
                        "chunk_index": chunk.index,
                        "text": chunk.text,
                        "fetched_at": source.fetched_at.isoformat(),
                    },
                )
                for chunk, vector in zip(chunks, embedded.vectors, strict=True)
            ],
        )
        return embedded.usage

    async def embed_queries(
        self, texts: list[str], *, agent: Agent
    ) -> tuple[list[list[float]], Usage]:
        """Embed many queries in one batched call (then search each with `search_vector`)."""
        if not texts:
            return [], Usage()
        embedded = await self._llm.embed(texts, agent=agent)
        return embedded.vectors, embedded.usage

    @retriever_span(name="qdrant.search_vector")
    async def search_vector(
        self,
        vector: list[float],
        *,
        source_ids: list[str] | None = None,
        exclude_source_ids: list[str] | None = None,
        limit: int = 5,
    ) -> list[ChunkHit]:
        must: list[models.Condition] = [_any("source_id", source_ids)] if source_ids else []
        must_not: list[models.Condition] = (
            [_any("source_id", exclude_source_ids)] if exclude_source_ids else []
        )
        response = await self._client.query_points(
            self.sources,
            query=vector,
            query_filter=models.Filter(must=must, must_not=must_not),
            limit=limit,
            with_payload=True,
        )
        return [
            ChunkHit(
                source_id=p.payload["source_id"],
                url=p.payload["url"],
                domain=p.payload["domain"],
                chunk_index=p.payload["chunk_index"],
                text=p.payload["text"],
                score=p.score,
            )
            for p in response.points
            if p.payload is not None
        ]

    @retriever_span(name="qdrant.search")
    async def search(
        self,
        query: str,
        *,
        agent: Agent,
        source_ids: list[str] | None = None,
        exclude_source_ids: list[str] | None = None,
        limit: int = 5,
    ) -> tuple[list[ChunkHit], Usage]:
        vectors, usage = await self.embed_queries([query], agent=agent)
        hits = await self.search_vector(
            vectors[0], source_ids=source_ids, exclude_source_ids=exclude_source_ids, limit=limit
        )
        return hits, usage


def _match(field: str, value: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key=field, match=models.MatchValue(value=value))]
    )


def _any(field: str, values: list[str]) -> models.FieldCondition:
    return models.FieldCondition(key=field, match=models.MatchAny(any=values))
