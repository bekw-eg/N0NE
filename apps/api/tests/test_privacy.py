"""Offline privacy checks use public catalog points, never a user's GPS position."""

import json
import logging
from math import asin, cos, radians, sin, sqrt
from typing import get_args

import h3
import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from app.core.config import ROOT, Settings
from app.main import create_app
from app.repositories.poi_repository import POIRepository
from app.schemas.privacy import (
    H3AnchorMatch,
    H3NoNearbyAnchor,
    H3ResolveRequest,
    H3ResolveResponse,
)
from app.schemas.routes import AnchorID
from app.services.privacy_service import SUPPORTED_AREA, PrivacyService

URL = "/api/v1/privacy/resolve-h3"


@pytest.fixture(scope="module")
def service() -> PrivacyService:
    return PrivacyService(Settings())


def anchor_cell(
    service: PrivacyService, anchor_id: AnchorID = "expo_nur_alem", res: int = 8
) -> str:
    point = service.anchors[anchor_id].location
    return h3.latlng_to_cell(point.latitude, point.longitude, res)


@pytest.mark.parametrize("anchor_id", get_args(AnchorID))
def test_public_anchor_cells(
    client: TestClient, service: PrivacyService, anchor_id: AnchorID
) -> None:
    cell = anchor_cell(service, anchor_id)
    response = client.post(URL, json={"h3_cell": cell})
    assert response.status_code == 200
    result = H3AnchorMatch.model_validate(response.json())
    assert result.start_anchor_id == anchor_id and result.resolution == 8
    assert response.headers["cache-control"] == "no-store"
    assert result.warnings == ["approximate_location", "anchor_distance_not_walking_distance"]

    # Independently check the straight-line estimate from center, not original point.
    lat, lng = h3.cell_to_latlng(cell)
    anchor = service.anchors[anchor_id].location
    a = (
        sin(radians(anchor.latitude - lat) / 2) ** 2
        + cos(radians(lat))
        * cos(radians(anchor.latitude))
        * sin(radians(anchor.longitude - lng) / 2) ** 2
    )
    assert result.distance_estimate_m == round(2 * 6371000 * asin(sqrt(a)))
    assert 0 < result.distance_estimate_m <= 3000


@pytest.mark.parametrize(
    "cell",
    [
        "invalid",
        "0" * 15,
        "f" * 15,
        "g" * 15,
        pytest.param("x" * 100000, id="oversized-body"),
        "",
        None,
        True,
        123,
        [],
        {},
        "882153806dfffff\n",
        " 882153806dfffff",
    ],
)
def test_malformed_cell(client: TestClient, cell: object) -> None:
    response = client.post(URL, json={"h3_cell": cell})
    assert response.status_code == (413 if isinstance(cell, str) and len(cell) > 16384 else 422)
    assert "input" not in response.text


def test_string_length_bound(client: TestClient, service: PrivacyService) -> None:
    cell = anchor_cell(service)
    for invalid in (cell[:-1], cell + "f", "a" * 256):
        response = client.post(URL, json={"h3_cell": invalid})
        assert response.status_code == 422 and invalid not in response.text


@pytest.mark.parametrize("resolution", [0, 7, 9, 15])
def test_resolution_must_be_exactly_eight(
    client: TestClient, service: PrivacyService, resolution: int
) -> None:
    cell = anchor_cell(service, res=resolution)
    response = client.post(URL, json={"h3_cell": cell})
    assert response.status_code == 422
    assert cell not in response.text


def test_edges_and_vertices_are_not_cells(client: TestClient, service: PrivacyService) -> None:
    cell = anchor_cell(service)
    neighbor = next(index for index in h3.grid_disk(cell, 1) if index != cell)
    edge = h3.cells_to_directed_edge(cell, neighbor)
    vertex = h3.cell_to_vertex(cell, 0)
    assert h3.is_valid_directed_edge(edge) and h3.is_valid_vertex(vertex)
    for index in (edge, vertex):
        assert client.post(URL, json={"h3_cell": index}).status_code == 422


def test_outside_astana(client: TestClient) -> None:
    # Public Eiffel Tower landmark, not personal geolocation.
    cell = h3.latlng_to_cell(48.85837, 2.294481, 8)
    response = client.post(URL, json={"h3_cell": cell})
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "no_nearby_anchor",
        "reason": "outside_supported_area",
        "resolution": 8,
        "warnings": ["approximate_location", "manual_anchor_selection_required"],
    }
    H3NoNearbyAnchor.model_validate(body)
    assert "start_anchor_id" not in body and "distance_estimate_m" not in body


def test_cell_center_defines_supported_area(client: TestClient, repository: POIRepository) -> None:
    # A public POI is inside the box, but its coarse cell center can fall outside.
    poi = repository.by_id["osm:node:4452020489"]
    assert SUPPORTED_AREA.contains(poi.latitude, poi.longitude)
    cell = h3.latlng_to_cell(poi.latitude, poi.longitude, 8)
    assert not SUPPORTED_AREA.contains(*h3.cell_to_latlng(cell))
    assert client.post(URL, json={"h3_cell": cell}).json()["reason"] == "outside_supported_area"


def test_no_anchor_within_configured_radius(
    repository: POIRepository, service: PrivacyService
) -> None:
    with TestClient(create_app(Settings(privacy_max_anchor_distance_m=100), repository)) as client:
        response = client.post(URL, json={"h3_cell": anchor_cell(service)})
        assert response.status_code == 200
        assert response.json() == {
            "status": "no_nearby_anchor",
            "reason": "no_anchor_within_radius",
            "resolution": 8,
            "warnings": ["approximate_location", "manual_anchor_selection_required"],
        }


def test_distance_threshold_before_rounding(service: PrivacyService) -> None:
    request = H3ResolveRequest(h3_cell=anchor_cell(service))
    matched = service.resolve(request)
    assert isinstance(matched, H3AnchorMatch)
    # EXPO center distance is ~394.37 m; both thresholds round to 394.
    limited = PrivacyService(Settings(privacy_max_anchor_distance_m=394.1))
    assert limited.resolve(request).status == "no_nearby_anchor"
    limited = PrivacyService(Settings(privacy_max_anchor_distance_m=394.5))
    assert limited.resolve(request).status == "matched"


def test_deterministic_choice_and_tie_breaking(service: PrivacyService) -> None:
    request = H3ResolveRequest(h3_cell=anchor_cell(service))
    original = service.resolve(request)
    reversed_service = PrivacyService(Settings())
    reversed_service.anchors = dict(reversed(list(reversed_service.anchors.items())))
    assert all(reversed_service.resolve(request) == original for _ in range(5))
    # Equal locations create an exact tie; ID ordering must win in any order.
    for anchor in reversed_service.anchors.values():
        anchor.location = service.anchors["expo_nur_alem"].location.model_copy()
    tied = reversed_service.resolve(request)
    assert isinstance(tied, H3AnchorMatch) and tied.start_anchor_id == "botanical_garden"


@pytest.mark.parametrize(
    "extra",
    [
        {"latitude": 51.089252},
        {"longitude": 71.4161925},
        {"gps": {"latitude": 51.089252, "longitude": 71.4161925}},
        {"coordinates": [71.4161925, 51.089252]},
        {"resolution": 9},
        {"start_anchor_id": "expo_nur_alem"},
        {"extra": "untrusted-secret-input"},
    ],
)
def test_extra_fields_rejected(
    client: TestClient, service: PrivacyService, extra: dict[str, object]
) -> None:
    response = client.post(URL, json={"h3_cell": anchor_cell(service), **extra})
    assert response.status_code == 422
    assert not any(
        value in response.text for value in ("51.089252", "71.4161925", "untrusted-secret")
    )
    assert all("input" not in error for error in response.json()["detail"])


@pytest.mark.parametrize("body", [{}, [], None, {"gps": [51.089252, 71.4161925]}])
def test_missing_body_or_cell(client: TestClient, body: object) -> None:
    assert client.post(URL, json=body).status_code == 422


@pytest.mark.parametrize("query", ["latitude=51.1", "gps=51,71", "h3_cell=882153806dfffff"])
def test_query_parameters_rejected(client: TestClient, service: PrivacyService, query: str) -> None:
    response = client.post(f"{URL}?{query}", json={"h3_cell": anchor_cell(service)})
    assert response.status_code == 422
    assert response.json() == {"detail": "Query parameters are not supported"}


def test_no_sensitive_values_in_responses_or_logs(
    client: TestClient, service: PrivacyService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    cell = anchor_cell(service)
    poi = service.anchors["expo_nur_alem"].location
    lat, lng = h3.cell_to_latlng(cell)
    requests = [
        {"h3_cell": cell},
        {"h3_cell": cell, "gps": {"latitude": poi.latitude, "longitude": poi.longitude}},
        {"h3_cell": "invalid-sensitive-cell"},
    ]
    for request in requests:
        response = client.post(URL, json=request)
        output = response.text + caplog.text
        assert all(
            value not in output
            for value in (
                cell,
                str(poi.latitude),
                str(poi.longitude),
                str(lat),
                str(lng),
                "invalid-sensitive-cell",
            )
        )
    assert cell not in repr(H3ResolveRequest(h3_cell=cell))
    with pytest.raises(ValidationError) as error:
        H3ResolveRequest(h3_cell="invalid-sensitive-cell")
    assert "invalid-sensitive-cell" not in str(error.value)


def test_privacy_does_not_call_other_services(
    client: TestClient, service: PrivacyService, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Privacy resolution must not call network, routing, RAG or weather")

    monkeypatch.setattr(client.app.state.route_planner, "plan", forbidden)
    monkeypatch.setattr(client.app.state.rag_service, "query", forbidden)
    monkeypatch.setattr(client.app.state.weather_service, "get_weather", forbidden)
    response = client.post(URL, json={"h3_cell": anchor_cell(service)})
    assert response.status_code == 200 and response.json()["status"] == "matched"
    assert set(vars(client.app.state.privacy_service)) == {"anchors", "max_distance_m"}


@pytest.mark.parametrize("limit", [0, -1, 10001, float("nan"), float("inf")])
def test_invalid_configuration(limit: float) -> None:
    with pytest.raises(ValidationError):
        Settings(privacy_max_anchor_distance_m=limit)


def test_openapi_and_committed_contract(client: TestClient) -> None:
    document = client.get("/openapi.json").json()
    operation = document["paths"][URL]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/H3ResolveRequest"
    }
    request = document["components"]["schemas"]["H3ResolveRequest"]
    assert request["additionalProperties"] is False
    assert request["required"] == ["h3_cell"] and list(request["properties"]) == ["h3_cell"]
    assert request["properties"]["h3_cell"]["maxLength"] == 15
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["discriminator"]["propertyName"] == "status"
    assert "422" in operation["responses"]
    expected = TypeAdapter(H3ResolveResponse).json_schema()
    expected["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    expected["$defs"]["H3ResolveRequest"] = H3ResolveRequest.model_json_schema()
    assert json.loads((ROOT / "contracts/privacy.schema.json").read_bytes()) == expected
