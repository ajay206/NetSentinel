from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from .chunking import Chunk

_NAMESPACE_URL = uuid.NAMESPACE_URL


class VectorStore:
    def __init__(
        self,
        url: str | None = None,
        path: str | None = None,
        collection: str = "runbooks",
    ) -> None:
        self.collection = collection
        if url:
            self.client = QdrantClient(url=url)
        elif path:
            self.client = QdrantClient(path=path)
        else:
            self.client = QdrantClient(location=":memory:")

    def ensure_collection(self, dim: int) -> None:
        if self.client.collection_exists(self.collection):
            params = self.client.get_collection(self.collection).config.params.vectors
            if getattr(params, "size", None) == dim:
                return
            self.client.delete_collection(self.collection)
        self._create(dim)

    def _create(self, dim: int) -> None:
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=rest.VectorParams(
                size=dim,
                distance=rest.Distance.COSINE,
            ),
        )

    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        points = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            point_id = str(uuid.uuid5(_NAMESPACE_URL, chunk.chunk_id))
            points.append(
                rest.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "runbook_id": chunk.runbook_id,
                        "title": chunk.title,
                        "section": chunk.section,
                        "text": chunk.text,
                        "fault_type": chunk.fault_type,
                    },
                )
            )
        self.client.upsert(self.collection, points)
        return len(points)

    def delete_missing(self, keep_ids: set[str]) -> int:
        """Delete points whose chunk_id is not in keep_ids (pages through the whole collection)."""
        stale: list = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection,
                with_payload=["chunk_id"],
                with_vectors=False,
                limit=256,
                offset=offset,
            )
            for point in points:
                chunk_id = point.payload.get("chunk_id") if point.payload else None
                if chunk_id not in keep_ids:
                    stale.append(point.id)
            if offset is None:
                break
        if stale:
            self.client.delete(
                collection_name=self.collection,
                points_selector=rest.PointIdsList(points=stale),
            )
        return len(stale)

    def search(self, vector: list[float], limit: int = 10) -> list[tuple[dict[str, Any], float]]:
        results = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        return [(hit.payload, hit.score) for hit in results.points]

    def count(self) -> int:
        return self.client.count(self.collection).count
