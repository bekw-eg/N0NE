import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from conftest import NOW
from pydantic import ValidationError
from viberoute_geo import (
    DirectionsRequest,
    GeoAdapter,
    GeoError,
    GeoPoint,
    IsochronesRequest,
    MatrixRequest,
)
from viberoute_geo.adapter import recording_name


def adapter_for(document: object, **kwargs: Any) -> GeoAdapter:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=document))
    )
    return GeoAdapter(api_key="SYNTHETIC-SECRET", client=client, now=lambda: NOW, **kwargs)


def test_directions_request_headers_units_and_geometry(
    points: list[GeoPoint], route: dict[str, Any]
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/directions/foot-walking/geojson"
        assert "api_key" not in request.url.params
        assert request.headers["Authorization"] == "SYNTHETIC-SECRET"
        assert json.loads(request.content) == {
            "coordinates": [[71.4, 51.1], [71.401, 51.101]],
            "radiuses": [100.0, 100.0],
            "elevation": False,
            "instructions": False,
            "units": "m",
        }
        return httpx.Response(200, json=route)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = GeoAdapter(api_key="SYNTHETIC-SECRET", client=client).directions(
            DirectionsRequest(locations=points)
        )
    assert result.duration_seconds == 145.2
    assert result.distance_meters == 180.5
    assert len(result.geojson.features[0].geometry.coordinates) == 3
    assert result.provenance.mode == "live"  # Test transport only, not a real provider call.
    assert result.provenance.profile == "foot-walking"


def test_isochrones_request_is_time_in_seconds(
    points: list[GeoPoint], isochrones: dict[str, Any]
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/isochrones/foot-walking"
        assert json.loads(request.content) == {
            "locations": [[71.4, 51.1]],
            "range": [600, 900],
            "range_type": "time",
        }
        return httpx.Response(200, json=isochrones)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = GeoAdapter(api_key="TEST", client=client).isochrones(
            IsochronesRequest(origin=points[0])
        )
    assert [feature.properties.value for feature in result.geojson.features] == [600, 900]


def test_matrix_preserves_direction_and_unreachable_pairs(
    points: list[GeoPoint], matrix: dict[str, Any]
) -> None:
    matrix["durations"][0][1] = None
    matrix["distances"][0][1] = None
    result = adapter_for(matrix).matrix(MatrixRequest(locations=points))
    assert result.data.durations == [[0, None], [160.1, 0]]
    assert result.data.distances[0][1] is None
    assert result.source_indices == [0, 1]


def test_rectangular_matrix_uses_requested_indices(
    points: list[GeoPoint], matrix: dict[str, Any]
) -> None:
    matrix["durations"] = [[160.1]]
    matrix["distances"] = [[195.1]]
    matrix["sources"] = [matrix["sources"][1]]
    matrix["destinations"] = [matrix["destinations"][0]]

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["sources"] == ["1"] and body["destinations"] == ["0"]
        assert body["metrics"] == ["duration", "distance"] and body["units"] == "m"
        return httpx.Response(200, json=matrix)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = GeoAdapter(api_key="TEST", client=client).matrix(
            MatrixRequest(locations=points, sources=[1], destinations=[0])
        )
    assert result.data.durations == [[160.1]]
    assert result.source_indices == [1] and result.destination_indices == [0]


@pytest.mark.parametrize(
    "change",
    ["empty", "negative", "bad_index", "bad_coordinate", "wrong_geometry", "wrong_waypoint_count"],
)
def test_malformed_routes_fail(points: list[GeoPoint], route: dict[str, Any], change: str) -> None:
    if change == "empty":
        route["features"] = []
    elif change == "negative":
        route["features"][0]["properties"]["summary"]["duration"] = -1
    elif change == "bad_index":
        route["features"][0]["properties"]["way_points"] = [0, 999]
    elif change == "bad_coordinate":
        route["features"][0]["geometry"]["coordinates"][0] = [181, 51.1]
    elif change == "wrong_geometry":
        route["features"][0]["geometry"]["type"] = "Polygon"
    else:
        route["features"][0]["properties"]["way_points"] = [0, 1, 2]
    with pytest.raises(GeoError) as error:
        adapter_for(route).directions(DirectionsRequest(locations=points))
    assert error.value.code == "invalid_response"


@pytest.mark.parametrize("change", ["open_ring", "missing_range", "wrong_range", "wrong_group"])
def test_malformed_isochrones_fail(
    points: list[GeoPoint], isochrones: dict[str, Any], change: str
) -> None:
    if change == "open_ring":
        isochrones["features"][0]["geometry"]["coordinates"][0][-1] = [71.405, 51.105]
    elif change == "missing_range":
        isochrones["features"].pop()
    elif change == "wrong_group":
        isochrones["features"][0]["properties"]["group_index"] = 1
    else:
        isochrones["features"][0]["properties"]["value"] = 500
    with pytest.raises(GeoError):
        adapter_for(isochrones).isochrones(IsochronesRequest(origin=points[0]))


@pytest.mark.parametrize("change", ["rows", "columns", "negative", "mismatched_null", "unsnapped"])
def test_malformed_matrices_fail(
    points: list[GeoPoint], matrix: dict[str, Any], change: str
) -> None:
    if change == "rows":
        matrix["durations"].pop()
    elif change == "columns":
        matrix["distances"][0].pop()
    elif change == "negative":
        matrix["durations"][0][1] = -5
    elif change == "mismatched_null":
        matrix["durations"][0][1] = None
    else:
        matrix["sources"][0] = None
    with pytest.raises(GeoError):
        adapter_for(matrix).matrix(MatrixRequest(locations=points))


def test_record_replay_exact_match_integrity_age_and_secret_redaction(
    points: list[GeoPoint], route: dict[str, Any], tmp_path: Path
) -> None:
    route["metadata"]["query"] = {"api_key": "SYNTHETIC-SECRET"}
    route["metadata"]["debug"] = "SYNTHETIC-SECRET"
    request = DirectionsRequest(locations=points)
    result = adapter_for(route, recordings_dir=tmp_path).directions(request)
    path = tmp_path / recording_name("directions", request.payload())
    assert "SYNTHETIC-SECRET" not in path.read_text(encoding="utf-8")
    offline = GeoAdapter(mode="recorded", recordings_dir=tmp_path, now=lambda: NOW)
    replay = offline.directions(request)
    assert replay.geojson == result.geojson
    assert replay.provenance.mode == "recorded" and replay.provenance.retrieved_at == NOW
    with pytest.raises(GeoError) as error:
        offline.directions(DirectionsRequest(locations=points, snap_radius_m=150))
    assert error.value.code == "recording_unavailable"
    with pytest.raises(GeoError) as error:
        GeoAdapter(
            mode="recorded", recordings_dir=tmp_path, now=lambda: NOW + timedelta(days=2)
        ).directions(request)
    assert error.value.code == "recording_stale"
    document = json.loads(path.read_bytes())
    document["response"]["features"][0]["properties"]["summary"]["duration"] = 1
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(GeoError) as error:
        offline.directions(request)
    assert error.value.code == "recording_corrupt"


def test_invalid_route_is_never_saved(
    points: list[GeoPoint], route: dict[str, Any], tmp_path: Path
) -> None:
    route["features"] = []
    with pytest.raises(GeoError):
        adapter_for(route, recordings_dir=tmp_path).directions(DirectionsRequest(locations=points))
    assert not list(tmp_path.iterdir())


def test_no_key_fails_without_network_or_geometry(points: list[GeoPoint]) -> None:
    with pytest.raises(GeoError) as error:
        GeoAdapter().directions(DirectionsRequest(locations=points))
    assert error.value.code == "configuration_missing"


@pytest.mark.parametrize("status", [401, 403, 429, 400, 503, 302])
def test_provider_errors_are_controlled_and_bounded(points: list[GeoPoint], status: int) -> None:
    requests: list[httpx.Request] = []
    sleeps: list[float] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json={"error": {"code": 2010, "message": "SYNTHETIC-SECRET"}})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(GeoError) as error:
            GeoAdapter(api_key="SYNTHETIC-SECRET", client=client, sleep=sleeps.append).directions(
                DirectionsRequest(locations=points)
            )
    assert "SYNTHETIC-SECRET" not in str(error.value)
    assert error.value.status == status and error.value.provider_code == 2010
    assert len(requests) == (3 if status in {429, 503} else 1)


def test_retry_after_is_capped(points: list[GeoPoint], route: dict[str, Any]) -> None:
    sleeps: list[float] = []

    def handle(_: httpx.Request) -> httpx.Response:
        return (
            httpx.Response(429, headers={"Retry-After": "120"})
            if not sleeps
            else httpx.Response(200, json=route)
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        GeoAdapter(api_key="TEST", client=client, sleep=sleeps.append).directions(
            DirectionsRequest(locations=points)
        )
    assert sleeps == [30.0]


def test_transport_failure_never_returns_a_straight_line(points: list[GeoPoint]) -> None:
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("SYNTHETIC-SECRET", request=request)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(GeoError) as error:
            GeoAdapter(api_key="SYNTHETIC-SECRET", client=client, sleep=lambda _: None).directions(
                DirectionsRequest(locations=points)
            )
    assert error.value.code == "transport_error" and len(calls) == 3
    assert "SYNTHETIC-SECRET" not in str(error.value)


@pytest.mark.parametrize("document", [[], {"error": {"code": 1}}, {"features": float("nan")}])
def test_invalid_success_payloads_rejected(points: list[GeoPoint], document: object) -> None:
    # json.dumps is deliberate: strict httpx json= rejects NaN before the adapter sees it.
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=json.dumps(document)))
    ) as client:
        with pytest.raises(GeoError):
            GeoAdapter(api_key="TEST", client=client).directions(
                DirectionsRequest(locations=points)
            )


@pytest.mark.parametrize("indices", [[], [2], [0, 0], [-1], [True]])
def test_invalid_matrix_indices_rejected(points: list[GeoPoint], indices: list[int]) -> None:
    with pytest.raises(ValidationError):
        MatrixRequest(locations=points, sources=indices)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 181, True, "71.4"])
def test_invalid_coordinates_rejected(value: object) -> None:
    with pytest.raises(ValidationError):
        GeoPoint(longitude=value, latitude=51.1)


@pytest.mark.parametrize("ranges", [(900, 600), (600, 600), (1200,), (), (True,)])
def test_invalid_ranges_rejected(points: list[GeoPoint], ranges: tuple[int, ...]) -> None:
    with pytest.raises(ValidationError):
        IsochronesRequest(origin=points[0], ranges_seconds=ranges)


def test_base_url_cannot_expose_a_key_in_url() -> None:
    for url in (
        "http://api.openrouteservice.org",
        "https://api.openrouteservice.org?api_key=secret",
        "https://user:secret@example.com",
    ):
        with pytest.raises(ValueError):
            GeoAdapter(base_url=url)
