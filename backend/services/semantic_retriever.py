"""Hybrid semantic retrieval for local POI recall.

This module now has a clearer production shape:

- lexical retrieval via a lightweight BM25 index
- dense retrieval via a deterministic local hash embedding
- optional FAISS acceleration when available
- optional external dense model hook for future BGE-style upgrades

The public API stays intentionally small so the rest of the route-planning
pipeline does not care whether the retrieval backend is local-only or upgraded
with stronger vector infrastructure later.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from core.route_policy import ROUTE_POLICY
from core.semantic_ontology import expand_canonical_targets
from core.schemas import POI, ParsedIntent
from core.text_tokenizer import normalize_compact, segmented_tokens
from services import model_backends

try:  # pragma: no cover - optional dependency
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    np = None

try:  # pragma: no cover - optional dependency
    import faiss  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    faiss = None


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]", re.UNICODE)
_RETRIEVAL_POLICY = dict((ROUTE_POLICY.get("retrieval") or {}))
_BACKEND_POLICY = dict((_RETRIEVAL_POLICY.get("backend") or {}))
_INDEX_CACHE: dict[tuple[str, ...], "HybridPoiIndex"] = {}


def _normalize(text: str) -> str:
    segmented = segmented_tokens(text)
    if segmented:
        return " ".join(segmented)
    return " ".join(_TOKEN_RE.findall((text or "").lower()))


def _ngrams(text: str) -> Counter[str]:
    normalized = _normalize(text)
    compact = normalize_compact(normalized)
    grams: Counter[str] = Counter()
    for token in normalized.split():
        if len(token) >= 2:
            grams[f"tok:{token}"] += 2
        elif token:
            grams[f"uni:{token}"] += 1
    for size in (2, 3):
        if len(compact) >= size:
            for index in range(len(compact) - size + 1):
                grams[f"c{size}:{compact[index:index + size]}"] += 1
    return grams


def _dense_terms(text: str) -> Counter[str]:
    normalized = _normalize(text)
    compact = normalize_compact(normalized)
    terms: Counter[str] = Counter()
    for token in normalized.split():
        if not token:
            continue
        if len(token) >= 2:
            terms[f"tok:{token}"] += 3
        else:
            terms[f"uni:{token}"] += 1
    for size in (2, 3, 4):
        if len(compact) >= size:
            for index in range(len(compact) - size + 1):
                terms[f"c{size}:{compact[index:index + size]}"] += 1
    return terms


def poi_text(poi: POI) -> str:
    fields = [
        poi.name or "",
        poi.category or "",
        poi.sub_category or "",
        poi.description or "",
        poi.address or "",
        poi.business_area or "",
        poi.area_label or "",
        poi.district or "",
        " ".join(poi.tags or []),
        " ".join(poi.suitable_for or []),
        " ".join(poi.review_keywords or []),
        " ".join(getattr(poi, "positive_reviews", []) or []),
        " ".join(getattr(poi, "negative_reviews", []) or []),
    ]
    return " ".join(item for item in fields if item)


def intent_query(intent: ParsedIntent, query: str = "") -> str:
    pieces: list[str] = [query or getattr(intent, "original_query", "") or ""]
    for attr in ("city", "start_location", "notes", "route_strategy", "primary_party_type"):
        value = getattr(intent, attr, None)
        if value:
            pieces.append(str(value))
    for field_name in (
        "required_categories",
        "preferred_categories",
        "preferences",
        "soft_preferences",
        "avoid",
        "must_include",
        "unclassified_clues",
        "intent_tags",
        "semantic_hints",
        "party_types",
    ):
        values = getattr(intent, field_name, []) or []
        pieces.extend(str(item) for item in values if item)
    pieces.extend(expand_canonical_targets("category", list(getattr(intent, "required_categories", []) or [])))
    pieces.extend(expand_canonical_targets("category", list(getattr(intent, "preferred_categories", []) or [])))
    pieces.extend(expand_canonical_targets("preference", list(getattr(intent, "preferences", []) or [])))
    pieces.extend(expand_canonical_targets("avoid", list(getattr(intent, "avoid", []) or [])))
    return " ".join(pieces)


def _hash_index(term: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
    raw = int.from_bytes(digest, "little", signed=False)
    index = raw % max(dim, 1)
    sign = -1.0 if (raw >> 8) & 1 else 1.0
    return index, sign


def _clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class _DocLexical:
    poi: POI
    tf: Counter[str]
    length: int


@dataclass(frozen=True)
class _DocDense:
    poi: POI
    vector: Any


class BM25PoiIndex:
    def __init__(self, pois: list[POI], *, k1: float = 1.5, b: float = 0.75):
        self.pois = list(pois)
        self.k1 = float(k1)
        self.b = float(b)
        self.docs: list[_DocLexical] = []
        self.doc_freq: Counter[str] = Counter()
        lengths: list[int] = []
        for poi in self.pois:
            tf = _ngrams(poi_text(poi))
            length = max(sum(tf.values()), 1)
            lengths.append(length)
            self.doc_freq.update(tf.keys())
            self.docs.append(_DocLexical(poi=poi, tf=tf, length=length))
        self.doc_count = max(len(self.docs), 1)
        self.avg_length = sum(lengths) / max(len(lengths), 1)
        self.idf = {
            term: math.log(1.0 + ((self.doc_count - freq + 0.5) / (freq + 0.5)))
            for term, freq in self.doc_freq.items()
        }

    def score(self, query: str) -> dict[str, float]:
        query_terms = _ngrams(query)
        if not query_terms:
            return {}
        scores: dict[str, float] = {}
        for doc in self.docs:
            score = 0.0
            norm = self.k1 * (1.0 - self.b + self.b * (doc.length / max(self.avg_length, 1e-6)))
            for term, qtf in query_terms.items():
                tf = float(doc.tf.get(term, 0))
                if tf <= 0:
                    continue
                idf = self.idf.get(term, 0.0)
                score += idf * ((tf * (self.k1 + 1.0)) / (tf + norm)) * min(float(qtf), 2.0)
            if score > 0:
                scores[doc.poi.id] = score
        return scores


class HashDensePoiIndex:
    def __init__(self, pois: list[POI], *, dim: int = 384):
        self.pois = list(pois)
        self.external_provider = model_backends.get_dense_provider()
        external_dim = None
        if self.external_provider is not None:
            external_dim = self.external_provider.vector_dim()
        self.dim = max(64, int(external_dim or dim))
        self.docs: list[_DocDense] = []
        self._faiss_index = None
        self._faiss_ids: list[str] = []

        external_vectors = self._encode_external_docs()
        if external_vectors is not None and np is not None:
            for poi, vector in zip(self.pois, external_vectors):
                self.docs.append(_DocDense(poi=poi, vector=vector))
            self._matrix = external_vectors.astype("float32")
        elif np is not None:
            rows: list[Any] = []
            for poi in self.pois:
                vector = self._encode(poi_text(poi))
                self.docs.append(_DocDense(poi=poi, vector=vector))
                rows.append(vector)
            self._matrix = np.vstack(rows).astype("float32") if rows else np.zeros((0, self.dim), dtype="float32")
        else:
            self._matrix = None
            for poi in self.pois:
                self.docs.append(_DocDense(poi=poi, vector=self._encode(poi_text(poi))))

        self._init_faiss()

    def _encode_external_docs(self):
        if self.external_provider is None or np is None or not self.pois:
            return None
        try:
            vectors = self.external_provider.encode([poi_text(poi) for poi in self.pois])
        except Exception:
            return None
        if vectors is None:
            return None
        if hasattr(vectors, "astype"):
            return vectors.astype("float32")
        return None

    def _encode(self, text: str):
        if self.external_provider is not None and np is not None:
            try:
                vectors = self.external_provider.encode([text])
            except Exception:
                vectors = None
            if vectors is not None and len(vectors) > 0:
                return vectors[0]
        terms = _dense_terms(text)
        if np is not None:
            vector = np.zeros(self.dim, dtype="float32")
            for term, weight in terms.items():
                index, sign = _hash_index(term, self.dim)
                vector[index] += float(weight) * float(sign)
            norm = float(np.linalg.norm(vector))
            if norm > 0:
                vector /= norm
            return vector
        vector = [0.0] * self.dim
        for term, weight in terms.items():
            index, sign = _hash_index(term, self.dim)
            vector[index] += float(weight) * float(sign)
        norm = math.sqrt(sum(value * value for value in vector))
        if norm > 0:
            vector = [value / norm for value in vector]
        return vector

    def _init_faiss(self) -> None:
        enable_faiss = str(os.getenv("ROUTE_RETRIEVAL_ENABLE_FAISS", str(_BACKEND_POLICY.get("enable_faiss", "1")))).lower()
        if enable_faiss in {"0", "false", "no", "off"}:
            return
        if faiss is None or np is None or self._matrix is None or len(self.docs) == 0:
            return
        try:  # pragma: no cover - optional dependency path
            index = faiss.IndexFlatIP(self.dim)
            index.add(self._matrix)
            self._faiss_index = index
            self._faiss_ids = [doc.poi.id for doc in self.docs]
        except Exception:
            self._faiss_index = None
            self._faiss_ids = []

    def score(self, query: str) -> dict[str, float]:
        if not query.strip():
            return {}
        query_vector = self._encode(query)
        if self._faiss_index is not None and np is not None and hasattr(query_vector, "reshape"):
            try:  # pragma: no cover - optional dependency path
                scores, indices = self._faiss_index.search(query_vector.reshape(1, -1).astype("float32"), max(len(self.docs), 1))
                result: dict[str, float] = {}
                for score, index in zip(scores[0], indices[0]):
                    if index < 0 or index >= len(self._faiss_ids):
                        continue
                    if float(score) > 0:
                        result[self._faiss_ids[index]] = float(score)
                return result
            except Exception:
                pass

        result: dict[str, float] = {}
        if np is not None and self._matrix is not None and hasattr(query_vector, "dot"):
            raw = self._matrix.dot(query_vector)
            for doc, score in zip(self.docs, raw.tolist()):
                if float(score) > 0:
                    result[doc.poi.id] = float(score)
            return result

        for doc in self.docs:
            dot = 0.0
            for left, right in zip(query_vector, doc.vector):
                dot += float(left) * float(right)
            if dot > 0:
                result[doc.poi.id] = dot
        return result


class HybridPoiIndex:
    def __init__(self, pois: list[POI]):
        self.pois = list(pois)
        self.bm25 = BM25PoiIndex(
            self.pois,
            k1=float(_BACKEND_POLICY.get("bm25_k1", 1.5) or 1.5),
            b=float(_BACKEND_POLICY.get("bm25_b", 0.75) or 0.75),
        )
        self.dense = HashDensePoiIndex(
            self.pois,
            dim=int(_BACKEND_POLICY.get("hash_vector_dim", 384) or 384),
        )
        self.lexical_weight = float(_BACKEND_POLICY.get("lexical_weight", 0.72) or 0.72)
        self.dense_weight = float(_BACKEND_POLICY.get("dense_weight", 1.0) or 1.0)

    def lexical_scores(self, query: str) -> dict[str, float]:
        return self.bm25.score(query)

    def dense_scores(self, query: str) -> dict[str, float]:
        return self.dense.score(query)

    @staticmethod
    def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
        if not scores:
            return {}
        values = list(float(value) for value in scores.values())
        lower = min(values)
        upper = max(values)
        if upper <= lower:
            return {key: 1.0 for key in scores}
        return {key: _clip((float(value) - lower) / (upper - lower)) for key, value in scores.items()}

    def hybrid_scores(self, query: str) -> dict[str, float]:
        lexical = self._normalize_scores(self.lexical_scores(query))
        dense = self._normalize_scores(self.dense_scores(query))
        all_ids = set(lexical) | set(dense)
        merged: dict[str, float] = {}
        for poi_id in all_ids:
            merged[poi_id] = (
                self.lexical_weight * float(lexical.get(poi_id, 0.0))
                + self.dense_weight * float(dense.get(poi_id, 0.0))
            ) / max(self.lexical_weight + self.dense_weight, 1e-6)
        return merged

    def runtime_info(self) -> dict[str, Any]:
        dense_info = model_backends.dense_backend_info()
        return {
            "hybrid_backend": "bm25_plus_dense_hash",
            "lexical_backend": "bm25_ngram",
            "dense_backend": (
                "faiss_external_dense"
                if self.dense._faiss_index is not None and dense_info.get("active")
                else "faiss_hash_dense"
                if self.dense._faiss_index is not None
                else "external_dense"
                if dense_info.get("active")
                else "local_hash_dense"
            ),
            "faiss_enabled": bool(self.dense._faiss_index is not None),
            "vector_dim": int(self.dense.dim),
            "external_embedding_backend": dense_info.get("backend"),
            "external_embedding_model": dense_info.get("model"),
            "external_embedding_active": bool(dense_info.get("active")),
        }


def _cache_key(pois: list[POI]) -> tuple[str, ...]:
    return tuple(str(getattr(poi, "id", "")) for poi in pois)


def index_for(pois: list[POI]) -> HybridPoiIndex:
    key = _cache_key(pois)
    cached = _INDEX_CACHE.get(key)
    if cached is not None:
        return cached
    index = HybridPoiIndex(pois)
    _INDEX_CACHE[key] = index
    return index


def runtime_info(pois: list[POI]) -> dict[str, Any]:
    if not pois:
        return {
            "hybrid_backend": "bm25_plus_dense_hash",
            "lexical_backend": "bm25_ngram",
            "dense_backend": "local_hash_dense",
            "faiss_enabled": False,
            "vector_dim": int(_BACKEND_POLICY.get("hash_vector_dim", 384) or 384),
            "external_embedding_backend": model_backends.dense_backend_info().get("backend"),
            "external_embedding_model": model_backends.dense_backend_info().get("model"),
            "external_embedding_active": bool(model_backends.dense_backend_info().get("active")),
        }
    return index_for(pois).runtime_info()


def score_pois(pois: list[POI], query: str) -> dict[str, float]:
    if not pois or not query.strip():
        return {}
    return index_for(pois).dense_scores(query)


def hybrid_score_pois(pois: list[POI], query: str) -> dict[str, float]:
    if not pois or not query.strip():
        return {}
    return index_for(pois).hybrid_scores(query)


def score_lexical_pois(pois: list[POI], query: str) -> dict[str, float]:
    if not pois or not query.strip():
        return {}
    return index_for(pois).lexical_scores(query)


def top_pois(pois: list[POI], query: str, *, limit: int = 80, threshold: float = 0.03) -> list[tuple[POI, float]]:
    scores = score_pois(pois, query)
    by_id = {poi.id: poi for poi in pois}
    ranked = [
        (by_id[poi_id], score)
        for poi_id, score in scores.items()
        if poi_id in by_id and score >= threshold
    ]
    ranked.sort(key=lambda item: (-item[1], item[0].id))
    return ranked[:limit]


def top_lexical_pois(pois: list[POI], query: str, *, limit: int = 80, threshold: float = 0.0) -> list[tuple[POI, float]]:
    scores = score_lexical_pois(pois, query)
    by_id = {poi.id: poi for poi in pois}
    ranked = [
        (by_id[poi_id], score)
        for poi_id, score in scores.items()
        if poi_id in by_id and score >= threshold
    ]
    ranked.sort(key=lambda item: (-item[1], item[0].id))
    return ranked[:limit]


def top_hybrid_pois(pois: list[POI], query: str, *, limit: int = 80, threshold: float = 0.03) -> list[tuple[POI, float]]:
    scores = hybrid_score_pois(pois, query)
    by_id = {poi.id: poi for poi in pois}
    ranked = [
        (by_id[poi_id], score)
        for poi_id, score in scores.items()
        if poi_id in by_id and score >= threshold
    ]
    ranked.sort(key=lambda item: (-item[1], item[0].id))
    return ranked[:limit]
