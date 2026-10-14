from __future__ import annotations

import hashlib
import os
import re
import threading
from typing import Protocol

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")


class Embedder(Protocol):
    dim: int
    name: str

    def embed(self, texts: list[str]) -> np.ndarray: ...


class HashEmbedder:
    dim: int = 384
    name: str = "hash-384"

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            tokens = _TOKEN_RE.findall(text.lower())
            for token in tokens:
                for gram in self._char_ngrams(token):
                    bucket, sign = self._bucket(gram)
                    vectors[i, bucket] += 0.5 * sign
                bucket, sign = self._bucket(token)
                vectors[i, bucket] += sign
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return (vectors / norms).astype(np.float32)

    def _bucket(self, feature: str) -> tuple[int, float]:
        h = int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")
        # Low bits pick the bucket; an independent high bit picks the sign.
        return h % self.dim, 1.0 if (h >> 63) & 1 else -1.0

    @staticmethod
    def _char_ngrams(token: str, n: int = 3) -> list[str]:
        if len(token) < n:
            return [token]
        return [token[i : i + n] for i in range(len(token) - n + 1)]


class FastEmbedEmbedder:
    def __init__(self, model: str = "BAAI/bge-small-en-v1.5") -> None:
        self.model = model
        self._client: object | None = None
        self._lock = threading.Lock()

    @property
    def dim(self) -> int:
        return 384

    @property
    def name(self) -> str:
        return self.model

    def embed(self, texts: list[str]) -> np.ndarray:
        if self._client is None:
            with self._lock:  # /search runs in FastAPI's threadpool
                if self._client is None:
                    from fastembed import TextEmbedding

                    self._client = TextEmbedding(self.model)
        result = np.array(list(self._client.embed(texts)), dtype=np.float32)
        norms = np.linalg.norm(result, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return (result / norms).astype(np.float32)


def get_embedder() -> Embedder:
    name = os.environ.get("EMBEDDER", "hash")
    if name == "fastembed":
        return FastEmbedEmbedder()
    return HashEmbedder()
