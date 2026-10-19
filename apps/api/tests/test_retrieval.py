import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import ROOT, Settings
from app.integrations.ollama import ProviderError
from app.main import create_app
from app.repositories.poi_repository import POIRepository
from app.retrieval.lexical import BM25Index
from app.retrieval.text import is_pizza_place
from app.schemas.rag import SearchRequest
from app.services.retrieval_service import RetrievalService, reciprocal_rank_fusion


class FakeEmbeddings:
    model_id = "mock-embedding"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.fail = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.fail:
            raise ProviderError("embedding_unavailable")
        return [[1.0, 0.0] if "rafe" in text.casefold() else [0.0, 1.0] for text in texts]


@pytest.mark.parametrize("query", ["Rafe", "Астана-Экспо", "Ботаникалық бақ", "кафе", "саябақ"])
def test_real_multilingual_retrieval(query: str, repository: POIRepository) -> None:
    index = BM25Index(repository)
    hits = index.search(query)
    assert hits and hits == index.search(query)
    assert len({poi_id for poi_id, _ in hits}) == len(hits)
    assert all(poi_id in repository.by_id and score > 0 for poi_id, score in hits)
    assert index.search("zzzzzzzz_missing_poi") == []


def test_known_poi_rank_and_normalization(repository: POIRepository) -> None:
    index = BM25Index(repository)
    assert index.search("ＲＡＦＥ")[0][0] == "osm:node:1843876259"
    assert index.search("БОТАНИКАЛЫҚ") == index.search("Ботаникалық")


@pytest.mark.parametrize(
    "query",
    [
        "хочу пиццу",
        "Пиццерия",
        "пиццы",
        "pizza",
        "pizzeria",
        "Хочу пиццу в кафе",
    ],
)
def test_pizza_requests_return_source_matched_food_places(
    repository: POIRepository,
    query: str,
) -> None:
    search = RetrievalService(repository, Settings(semantic_enabled=False))
    result = search.search(SearchRequest(query=query, top_k=10))
    ids = {hit.poi.id for hit in result.results}
    # Known pizza names in the immutable OSM snapshot, across Russian and English.
    assert {"osm:node:11900510369", "osm:node:10171453646"} <= ids
    assert ids <= {
        "osm:node:5920104185",
        "osm:node:10171453646",
        "osm:node:11900510369",
        "osm:node:12917083082",
        "osm:node:14100100181",
    }
    assert all(
        hit.poi.category in {"cafe", "restaurant", "fast_food", "food_court"}
        for hit in result.results
    )


def test_pizza_match_requires_food_name_or_cuisine_evidence(repository: POIRepository) -> None:
    original = repository.records[0]
    cafe = original.model_copy(
        update={
            "category": "cafe",
            "name": "Cafe",
            "tags": {
                "cuisine": "italian;pizza",
            },
        }
    )
    assert is_pizza_place(cafe)
    no_evidence = cafe.model_copy(
        update={
            "tags": {
                "cuisine": "italian",
                "addr:street": "Pizza Street",
                "website": "https://pizza.test",
            }
        }
    )
    assert not is_pizza_place(no_evidence)
    assert not is_pizza_place(cafe.model_copy(update={"category": "artwork", "name": "Pizza"}))


def test_semantic_hits_cannot_replace_explicit_pizza_request(
    repository: POIRepository,
    tmp_path: Path,
) -> None:
    search = RetrievalService(
        repository,
        Settings(
            semantic_enabled=True,
            embedding_index_dir=tmp_path,
        ),
        FakeEmbeddings(),
    )
    result = search.search(SearchRequest(query="Rafe хочу пиццу", top_k=10))
    assert result.retrieval_mode == "hybrid"
    assert result.results
    assert "osm:node:1843876259" not in {hit.poi.id for hit in result.results}


def test_retrieval_response_and_nulls(client: TestClient, repository: POIRepository) -> None:
    original_hash = hashlib.sha256((ROOT / "data/astana/pois.json").read_bytes()).hexdigest()
    body = client.post("/api/v1/retrieval/search", json={"query": "Rafe", "top_k": 1}).json()
    assert body["query"] == "Rafe" and body["retrieval_mode"] == "lexical"
    assert "semantic_disabled" in body["warnings"]
    hit = body["results"][0]
    poi = hit["poi"]
    assert poi["id"] == "osm:node:1843876259"
    assert poi["opening_hours"] is None and poi["indoor"] is None
    assert hit["rank"] == 1 and hit["lexical_score"] > 0 and hit["semantic_score"] is None
    assert "opening_hours_unknown" in hit["warnings"]
    assert poi["provenance"] == repository.by_id[poi["id"]].provenance.model_dump(mode="json")
    assert body["dataset"]["dataset_sha256"] == original_hash
    assert body["dataset"]["attribution"] == "© OpenStreetMap contributors"
    assert (
        hashlib.sha256((ROOT / "data/astana/pois.json").read_bytes()).hexdigest() == original_hash
    )
    empty = client.post("/api/v1/retrieval/search", json={"query": "zzzzzz_missing"}).json()
    assert empty["results"] == [] and empty["dataset"]["license"] == "ODbL-1.0"


def test_rrf_uses_both_rankers_and_deduplicates() -> None:
    ranked = reciprocal_rank_fusion([("a", 8), ("b", 4), ("a", 2)], [("b", 0.9), ("c", 0.8)])
    assert [key for key, _ in ranked] == ["b", "a", "c"]
    assert ranked[0][1] == pytest.approx(1 / 62 + 1 / 61)
    assert reciprocal_rank_fusion([("b", 1)], [("a", 1)]) == [("a", 1 / 61), ("b", 1 / 61)]


def test_hybrid_and_query_time_failure(repository: POIRepository, tmp_path: Path) -> None:
    provider = FakeEmbeddings()
    config = Settings(semantic_enabled=True, embedding_index_dir=tmp_path)
    search = RetrievalService(repository, config, provider)
    result = search.search(SearchRequest(query="Rafe", top_k=3))
    assert result.retrieval_mode == "hybrid"
    assert result.results[0].poi.id == "osm:node:1843876259"
    assert result.results[0].semantic_score == pytest.approx(1)
    assert result.results[0].lexical_score is not None
    assert len({hit.poi.id for hit in result.results}) == len(result.results)
    provider.fail = True
    fallback = search.search(SearchRequest(query="Rafe"))
    assert fallback.retrieval_mode == "lexical"
    assert "embedding_unavailable" in fallback.warnings
    assert fallback.results[0].semantic_score is None


def test_startup_embedding_failure_is_visible(repository: POIRepository, tmp_path: Path) -> None:
    provider = FakeEmbeddings()
    provider.fail = True
    app = create_app(
        Settings(semantic_enabled=True, embedding_index_dir=tmp_path),
        repository,
        embedding_provider=provider,
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        result = client.post("/api/v1/retrieval/search", json={"query": "Rafe"}).json()
    assert result["retrieval_mode"] == "lexical"
    assert "embedding_unavailable" in result["warnings"]


@pytest.mark.parametrize("endpoint", ["retrieval/search", "rag/query"])
@pytest.mark.parametrize(
    "body",
    [
        {"query": ""},
        {"query": " \n "},
        {"query": "x" * 1001},
        {"query": "a", "top_k": 0},
        {"query": "a", "top_k": 11},
        {"query": "a", "language": "de"},
        {"query": "a", "latitude": 51.1},
    ],
)
def test_request_validation(endpoint: str, body: dict[str, object], client: TestClient) -> None:
    assert client.post(f"/api/v1/{endpoint}", json=body).status_code == 422


def test_body_byte_limit_including_streams(client: TestClient) -> None:
    response = client.post("/api/v1/rag/query", content=b" " * 17000)
    assert response.status_code == 413
    streamed = client.post("/api/v1/rag/query", content=iter([b" " * 9000, b" " * 9000]))
    assert streamed.status_code == 413
