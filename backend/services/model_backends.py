"""Optional external embedding and rerank backends.

The project should stay lightweight by default, but support stronger semantic
models when the environment is prepared for them.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

try:  # pragma: no cover - optional dependency
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    np = None

try:  # pragma: no cover - optional dependency
    from sentence_transformers import CrossEncoder, SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    CrossEncoder = None
    SentenceTransformer = None


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default)).strip()


def _backend_enabled(name: str) -> bool:
    value = _env(name, "none").lower()
    return value not in {"", "0", "false", "no", "none", "off"}


class DenseProvider:
    def __init__(self, *, backend: str, model_name: str):
        self.backend = backend
        self.model_name = model_name
        self._model = None

    def available(self) -> bool:
        return False

    def encode(self, texts: list[str]) -> Any:
        raise NotImplementedError

    def vector_dim(self) -> int | None:
        return None


class SentenceTransformerDenseProvider(DenseProvider):
    def __init__(self, *, model_name: str):
        super().__init__(backend="sentence_transformers", model_name=model_name)

    def available(self) -> bool:
        return SentenceTransformer is not None and np is not None

    def _load(self):
        if self._model is None and self.available():
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> Any:
        model = self._load()
        if model is None or np is None:
            return None
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vectors.astype("float32")

    def vector_dim(self) -> int | None:
        model = self._load()
        if model is None:
            return None
        try:
            return int(model.get_sentence_embedding_dimension())
        except Exception:
            return None


class RerankProvider:
    def __init__(self, *, backend: str, model_name: str):
        self.backend = backend
        self.model_name = model_name
        self._model = None

    def available(self) -> bool:
        return False

    def score_pairs(self, query: str, documents: list[str]) -> list[float]:
        raise NotImplementedError


class SentenceTransformerRerankProvider(RerankProvider):
    def __init__(self, *, model_name: str):
        super().__init__(backend="sentence_transformers", model_name=model_name)

    def available(self) -> bool:
        return CrossEncoder is not None

    def _load(self):
        if self._model is None and self.available():
            self._model = CrossEncoder(self.model_name)
        return self._model

    def score_pairs(self, query: str, documents: list[str]) -> list[float]:
        model = self._load()
        if model is None:
            return []
        pairs = [(query, document) for document in documents]
        raw_scores = model.predict(pairs, show_progress_bar=False)
        if hasattr(raw_scores, "tolist"):
            raw_scores = raw_scores.tolist()
        return [float(score) for score in raw_scores]


def _build_dense_provider() -> DenseProvider | None:
    backend = _env("ROUTE_DENSE_MODEL_BACKEND", "none").lower()
    model_name = _env("ROUTE_DENSE_MODEL", "BAAI/bge-m3")
    if not _backend_enabled("ROUTE_DENSE_MODEL_BACKEND"):
        return None
    if backend == "sentence_transformers":
        provider = SentenceTransformerDenseProvider(model_name=model_name)
        return provider if provider.available() else None
    return None


def _build_rerank_provider() -> RerankProvider | None:
    backend = _env("ROUTE_RERANK_MODEL_BACKEND", "none").lower()
    model_name = _env("ROUTE_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
    if not _backend_enabled("ROUTE_RERANK_MODEL_BACKEND"):
        return None
    if backend == "sentence_transformers":
        provider = SentenceTransformerRerankProvider(model_name=model_name)
        return provider if provider.available() else None
    return None


@lru_cache(maxsize=1)
def get_dense_provider() -> DenseProvider | None:
    try:
        return _build_dense_provider()
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_rerank_provider() -> RerankProvider | None:
    try:
        return _build_rerank_provider()
    except Exception:
        return None


def dense_backend_info() -> dict[str, Any]:
    backend = _env("ROUTE_DENSE_MODEL_BACKEND", "none").lower() or "none"
    model_name = _env("ROUTE_DENSE_MODEL", "")
    provider = get_dense_provider()
    return {
        "backend": provider.backend if provider is not None else backend,
        "model": provider.model_name if provider is not None else (model_name or None),
        "active": provider is not None,
        "vector_dim": provider.vector_dim() if provider is not None else None,
    }


def rerank_backend_info() -> dict[str, Any]:
    backend = _env("ROUTE_RERANK_MODEL_BACKEND", "none").lower() or "none"
    model_name = _env("ROUTE_RERANK_MODEL", "")
    provider = get_rerank_provider()
    return {
        "backend": provider.backend if provider is not None else backend,
        "model": provider.model_name if provider is not None else (model_name or None),
        "active": provider is not None,
        "max_items": max(1, int(_env("ROUTE_RERANK_MAX_ITEMS", "64") or "64")),
    }
