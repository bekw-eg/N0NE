"""Versioned, atomic local vector cache. This is a derived index, never source data."""

import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from app.core.config import Settings
from app.integrations.ollama import EmbeddingProvider, ProviderError
from app.retrieval.text import TEXT_VERSION
from app.schemas.poi import Model


def validate_vectors(value: object, count: int) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != count:
        raise ProviderError("embedding_invalid_response")
    vectors: list[list[float]] = []
    dimension = 0
    for vector in value:
        if not isinstance(vector, list) or not 1 <= len(vector) <= 8192:
            raise ProviderError("embedding_invalid_response")
        if dimension and dimension != len(vector):
            raise ProviderError("embedding_invalid_response")
        dimension = len(vector)
        if any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in vector
        ):
            raise ProviderError("embedding_invalid_response")
        norm = math.hypot(*vector)
        if not math.isfinite(norm) or norm == 0:
            raise ProviderError("embedding_invalid_response")
        vectors.append([float(v / norm) for v in vector])
    return vectors


class IndexFile(Model):
    version: Literal[1] = 1
    dataset_sha256: str
    model_id: str
    text_version: str
    texts_sha256: str
    ids: list[str]
    vectors: list[list[float]]


class SemanticIndex:
    def __init__(self, ids: list[str], vectors: list[list[float]]) -> None:
        self.ids = ids
        self.vectors = validate_vectors(vectors, len(ids))

    @classmethod
    def load_or_build(
        cls,
        documents: dict[str, str],
        dataset_hash: str,
        provider: EmbeddingProvider,
        settings: Settings,
    ) -> tuple["SemanticIndex", list[str]]:
        ids = list(documents)
        texts = list(documents.values())
        texts_hash = hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode()).hexdigest()
        key = hashlib.sha256(
            f"{dataset_hash}:{provider.model_id}:{TEXT_VERSION}".encode()
        ).hexdigest()
        path = settings.embedding_index_dir / f"{key}.json"
        metadata = {
            "dataset_sha256": dataset_hash,
            "model_id": provider.model_id,
            "text_version": TEXT_VERSION,
            "texts_sha256": texts_hash,
            "ids": ids,
        }
        try:
            cached = IndexFile.model_validate_json(path.read_bytes())
            if all(getattr(cached, key) == value for key, value in metadata.items()):
                return cls(ids, cached.vectors), []
        except (OSError, ValueError, ValidationError, ProviderError):
            pass  # Invalid caches are rebuilt; the source snapshot is never altered.
        vectors = []
        started = time.monotonic()
        for offset in range(0, len(texts), settings.embedding_batch_size):
            if time.monotonic() - started > settings.index_build_timeout_seconds:
                raise ProviderError("embedding_index_build_timeout")
            batch = texts[offset : offset + settings.embedding_batch_size]
            vectors.extend(validate_vectors(provider.embed(batch), len(batch)))
        index = cls(ids, vectors)
        cache = IndexFile.model_validate({**metadata, "vectors": index.vectors})
        warnings = []
        try:
            cls.save(path, cache)
        except OSError:
            warnings.append("embedding_cache_write_failed")
        return index, warnings

    @staticmethod
    def save(path: Path, cache: IndexFile) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
            ) as stream:
                temporary = stream.name
                stream.write(cache.model_dump_json())
            os.replace(temporary, path)
        finally:
            if temporary and Path(temporary).exists():
                Path(temporary).unlink()

    def search(self, query_vector: list[float], minimum: float) -> list[tuple[str, float]]:
        query = validate_vectors([query_vector], 1)[0]
        if self.vectors and len(query) != len(self.vectors[0]):
            raise ProviderError("embedding_dimension_mismatch")
        scored = [
            (poi_id, max(-1.0, min(1.0, sum(a * b for a, b in zip(vector, query, strict=True)))))
            for poi_id, vector in zip(self.ids, self.vectors, strict=True)
        ]
        return sorted(
            (item for item in scored if item[1] >= minimum), key=lambda item: (-item[1], item[0])
        )
