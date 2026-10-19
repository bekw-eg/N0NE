import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from viberoute_data.models import Dataset

from app.core.config import ROOT, Settings
from app.core.errors import DatasetLoadError
from app.dependencies import get_poi_service
from app.main import create_app
from app.repositories.poi_repository import POIRepository
from app.schemas.poi import PublicPOI
from app.services.poi_service import POIService


def test_startup_health_and_documentation(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/api/v1/pois/{poi_id}" in schema["paths"]


def test_all_497_real_pois_and_sources(repository: POIRepository, client: TestClient) -> None:
    raw = (ROOT / "data/astana/pois.json").read_bytes()
    original = Dataset.model_validate_json(raw)
    assert len(repository.items) == len(original.pois) == 497
    assert repository.metadata.dataset_sha256 == hashlib.sha256(raw).hexdigest()
    for poi in original.pois:
        public = repository.by_id[poi.id]
        assert public == PublicPOI.from_poi(poi, public.source)
        assert public.provenance == poi.provenance
        assert public.name == poi.name
        assert public.indoor is poi.attributes.indoor
        assert public.opening_hours == poi.opening_hours
        assert public.source.attribution == "© OpenStreetMap contributors"
        assert public.source.license == "ODbL-1.0"
    unnamed = next(poi for poi in repository.items if poi.name is None)
    result = client.get(f"/api/v1/pois/{unnamed.id}").json()
    assert result["name"] is None
    missing = next(poi for poi in repository.items if poi.opening_hours is None)
    result = client.get(f"/api/v1/pois/{missing.id}").json()
    assert result["opening_hours"] is None
    assert result["provenance"]["url"] == result["source_url"]


@pytest.mark.parametrize("query", ["Ботаникалық", "БОТАНИКАЛЫҚ", "Астана-Экспо", "rAfE"])
def test_unicode_and_casefold(query: str, client: TestClient) -> None:
    response = client.get("/api/v1/pois", params={"q": query})
    assert response.status_code == 200
    assert response.json()["total"] > 0


def test_category_pagination_and_empty(client: TestClient) -> None:
    first = client.get("/api/v1/pois", params={"limit": 3}).json()
    second = client.get("/api/v1/pois", params={"limit": 3, "offset": 3}).json()
    combined = client.get("/api/v1/pois", params={"limit": 6}).json()
    assert first["items"] + second["items"] == combined["items"]
    assert first["total"] == 497
    assert [p["id"] for p in combined["items"]] == sorted(p["id"] for p in combined["items"])
    cafes = client.get("/api/v1/pois", params={"category": "cafe"}).json()
    assert cafes["items"] and all(p["category"] == "cafe" for p in cafes["items"])
    assert cafes["dataset"]["license"] == "ODbL-1.0"
    for params in ({"q": "zzzz_no_such_poi"}, {"offset": 99999}):
        assert client.get("/api/v1/pois", params=params).json()["items"] == []
    assert client.get("/api/v1/pois/osm:node:1").status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"limit": "0"},
        {"limit": "101"},
        {"offset": "-1"},
        {"limit": "abc"},
        {"q": "x" * 201},
        {"category": "invented"},
        {"offset": "100001"},
    ],
)
def test_invalid_parameters(params: dict[str, str], client: TestClient) -> None:
    response = client.get("/api/v1/pois", params=params)
    assert response.status_code == 422
    assert "input" not in response.json()["detail"][0]


@pytest.mark.parametrize("payload", [None, b"{", b"{}", b'{"pois": []}'])
def test_bad_dataset_aborts_startup(tmp_path: Path, payload: bytes | None) -> None:
    target = tmp_path / "bad.json"
    if payload is not None:
        target.write_bytes(payload)
    with pytest.raises(DatasetLoadError), TestClient(create_app(Settings(poi_dataset_path=target))):
        pass


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    data = json.loads((ROOT / "data/astana/pois.json").read_bytes())
    data["pois"][1] = data["pois"][0]
    target = tmp_path / "duplicate.json"
    target.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(DatasetLoadError):
        POIRepository.load(target)


def test_no_file_read_per_request(repository: POIRepository, tmp_path: Path) -> None:
    target = tmp_path / "snapshot.json"
    target.write_bytes((ROOT / "data/astana/pois.json").read_bytes())
    app = create_app(Settings(poi_dataset_path=target))
    with TestClient(app) as client:
        target.unlink()
        assert client.get("/api/v1/pois").json()["total"] == 497
        app.dependency_overrides[get_poi_service] = lambda: POIService(repository)
        assert client.get("/api/v1/pois").json()["total"] == 497


def test_explicit_cors(repository: POIRepository) -> None:
    with pytest.raises(ValidationError):
        Settings(cors_origins=["*"])
    with TestClient(
        create_app(Settings(cors_origins=["http://localhost:3000"]), repository)
    ) as api:
        allowed = api.get("/health", headers={"Origin": "http://localhost:3000"})
        denied = api.get("/health", headers={"Origin": "https://untrusted.example"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in denied.headers


def test_contract_matches_generated_schema() -> None:
    committed = json.loads((ROOT / "contracts/poi.schema.json").read_bytes())
    assert committed == PublicPOI.model_json_schema()
