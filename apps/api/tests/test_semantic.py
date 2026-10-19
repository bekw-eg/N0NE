import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import Settings
from app.integrations.ollama import OllamaEmbeddings, ProviderError
from app.retrieval.semantic import SemanticIndex, validate_vectors


class RecordingEmbeddings:
    def __init__(self, model_id: str = "mock-v1") -> None:
        self.model_id = model_id
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[1.0, float(len(text))] for text in texts]


def test_cache_batching_hash_model_and_text_version(tmp_path: Path) -> None:
    config = Settings(embedding_index_dir=tmp_path, embedding_batch_size=2)
    provider = RecordingEmbeddings()
    documents = {"a": "Русский", "b": "Қазақша", "c": "English"}
    index, warnings = SemanticIndex.load_or_build(documents, "hash1", provider, config)
    assert warnings == []
    assert [len(batch) for batch in provider.calls] == [2, 1]
    assert index.ids == list(documents)
    assert index.search([1, 7], -1)[0][1] == pytest.approx(1)
    cached, _ = SemanticIndex.load_or_build(documents, "hash1", provider, config)
    assert len(provider.calls) == 2 and cached.vectors == index.vectors
    SemanticIndex.load_or_build(documents, "hash2", provider, config)
    assert len(provider.calls) == 4
    other = RecordingEmbeddings("mock-v2")
    SemanticIndex.load_or_build(documents, "hash2", other, config)
    assert len(other.calls) == 2 and len(list(tmp_path.glob("*.json"))) == 3
    changed = {**documents, "a": "Changed source text"}
    SemanticIndex.load_or_build(changed, "hash2", other, config)
    assert len(other.calls) == 4
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("change", ["invalid_json", "ids", "model_id", "text_version", "vectors"])
def test_corrupt_or_stale_cache_rebuilds(tmp_path: Path, change: str) -> None:
    provider = RecordingEmbeddings()
    config = Settings(embedding_index_dir=tmp_path)
    documents = {"a": "source"}
    SemanticIndex.load_or_build(documents, "hash", provider, config)
    target = next(tmp_path.glob("*.json"))
    data = json.loads(target.read_bytes())
    if change == "invalid_json":
        target.write_text("{", encoding="utf-8")
    else:
        data[change] = {
            "ids": ["unexpected"],
            "vectors": [[0, 0]],
            "model_id": "wrong",
            "text_version": "old",
        }[change]
        target.write_text(json.dumps(data), encoding="utf-8")
    index, _ = SemanticIndex.load_or_build(documents, "hash", provider, config)
    assert len(provider.calls) == 2 and index.ids == ["a"]


@pytest.mark.parametrize(
    "vectors,count",
    [
        (None, 1),
        ([[1, 0]], 2),
        ([[]], 1),
        ([[0, 0]], 1),
        ([[float("nan")]], 1),
        ([[float("inf")]], 1),
        ([[True, 1]], 1),
        ([["1"]], 1),
        ([[1], [1, 2]], 2),
    ],
)
def test_bad_embeddings_rejected(vectors: object, count: int) -> None:
    with pytest.raises(ProviderError):
        validate_vectors(vectors, count)


def test_cosine_math_dimension_and_threshold() -> None:
    index = SemanticIndex(["a", "b", "c"], [[3, 0], [0, 4], [-2, 0]])
    assert index.search([2, 0], 0.1) == [("a", 1)]
    assert index.search([2, 0], -1) == [("a", 1), ("b", 0), ("c", -1)]
    with pytest.raises(ProviderError, match="dimension_mismatch"):
        index.search([1, 2, 3], 0)


def test_embedding_rest_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        payload = json.loads(request.content)
        assert payload["input"] == ["Қазақша", "Русский"]
        assert payload["truncate"] is False
        return httpx.Response(200, json={"model": payload["model"], "embeddings": [[3, 4], [4, 3]]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        vectors = OllamaEmbeddings(Settings(), client).embed(["Қазақша", "Русский"])
    assert vectors[0] == [0.6, 0.8]


@pytest.mark.parametrize(
    "failure", ["timeout", "503", "invalid_json", "wrong_model", "bad_vectors"]
)
def test_embedding_rest_failures(failure: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("private diagnostic", request=request)
        if failure == "503":
            return httpx.Response(503)
        if failure == "invalid_json":
            return httpx.Response(200, content=b"{")
        return httpx.Response(
            200,
            json={
                "model": "wrong" if failure == "wrong_model" else "qwen3-embedding:0.6b",
                "embeddings": [[0, 0]] if failure == "bad_vectors" else [[1, 2]],
            },
        )

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ProviderError),
    ):
        OllamaEmbeddings(Settings(), client).embed(["Rafe"])


def test_index_build_deadline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A 1e-12 real timeout can elapse within one Windows monotonic clock tick.
    # Advance only this module's clock deterministically across the budget.
    ticks = iter([0.0, 2.0])
    monkeypatch.setattr(
        "app.retrieval.semantic.time", SimpleNamespace(monotonic=lambda: next(ticks))
    )
    with pytest.raises(ProviderError, match="build_timeout"):
        SemanticIndex.load_or_build(
            {"a": "text"},
            "hash",
            RecordingEmbeddings(),
            Settings(embedding_index_dir=tmp_path, index_build_timeout_seconds=1),
        )


def test_cache_write_failure_keeps_memory_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(path: Path, cache: object) -> None:
        raise OSError("read-only index directory")

    monkeypatch.setattr(SemanticIndex, "save", fail)
    index, warnings = SemanticIndex.load_or_build(
        {"a": "text"}, "hash", RecordingEmbeddings(), Settings(embedding_index_dir=tmp_path)
    )
    assert index.ids == ["a"] and warnings == ["embedding_cache_write_failed"]
