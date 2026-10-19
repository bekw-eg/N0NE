"""Offline integration against actual ORS captures, not synthetic geometry."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn

import httpx
import pytest
from viberoute_geo import cli
from viberoute_geo.adapter import canonical
from viberoute_geo.models import GeoCapture

from apps.api.app.integrations.geo_adapter import (
    DirectionsRequest,
    GeoAdapter,
    GeoError,
    IsochronesRequest,
    MatrixRequest,
)

ROOT = Path(__file__).resolve().parents[2]
RECORDINGS = ROOT / "data/geo/recordings"
CATALOG = ROOT / "shared/anchors.json"


def capture_time() -> datetime:
    return max(
        GeoCapture.model_validate_json(path.read_bytes()).retrieved_at
        for path in RECORDINGS.glob("*.json")
    )


def historical_catalog() -> cli.AnchorCatalog:
    # Exact historical requests must use their original points even as the current
    # catalog grows or replaces a center with an evidenced entrance.
    original = json.loads((ROOT / "data/geo/demo/anchors.json").read_bytes())
    return cli.AnchorCatalog.model_validate(
        {
            "schema_version": "0.1.0",
            "description": "Original PR #2 anchors, not current entrance evidence",
            "anchors": [original["origin"], original["destination"]],
        }
    )


def no_network(*args: Any, **kwargs: Any) -> NoReturn:
    raise AssertionError("Offline integration must not open an HTTP client")


def test_backend_facade_replays_all_real_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "Client", no_network)
    original = {path: path.read_bytes() for path in RECORDINGS.glob("*.json")}
    catalog = historical_catalog()
    points = [anchor.location for anchor in catalog.anchors]
    adapter = GeoAdapter(mode="recorded", recordings_dir=RECORDINGS, now=capture_time)
    route = adapter.directions(DirectionsRequest(locations=points))
    areas = adapter.isochrones(IsochronesRequest(origin=points[0]))
    matrix = adapter.matrix(MatrixRequest(locations=points))
    assert route.duration_seconds > 0 and route.distance_meters > 0
    assert len(route.geojson.features[0].geometry.coordinates) > 2
    assert {feature.properties.value for feature in areas.geojson.features} == {600, 900}
    assert all(result.provenance.mode == "recorded" for result in (route, areas, matrix))
    assert matrix.data.durations[0][1] is not None
    assert matrix.data.durations[1][0] is not None
    assert matrix.data.sources[0] is not None
    assert "openrouteservice" in route.provenance.metadata["attribution"].lower()
    for result, operation in zip(
        (route, areas, matrix), ("directions", "isochrones", "matrix"), strict=True
    ):
        path = next(RECORDINGS.glob(f"{operation}-*.json"))
        capture = GeoCapture.model_validate_json(original[path])
        assert result.provenance.endpoint == capture.endpoint
        assert str(result.provenance.endpoint).startswith("https://api.openrouteservice.org/v2/")
        assert result.provenance.retrieved_at == capture.retrieved_at
        assert result.provenance.metadata == capture.response.get("metadata", {})
    assert {path: path.read_bytes() for path in RECORDINGS.glob("*.json")} == original


@pytest.mark.parametrize(
    "change", ["endpoint", "request", "operation", "profile", "retrieved_at", "response", "hash"]
)
def test_historical_compatibility_rejects_modified_capture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, change: str
) -> None:
    monkeypatch.setattr(httpx, "Client", no_network)
    path = next(RECORDINGS.glob("directions-*.json"))
    capture = json.loads(path.read_bytes())
    if change == "endpoint":
        capture["endpoint"] = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    elif change == "request":
        capture["request"]["radiuses"] = [150, 150]
    elif change == "operation":
        capture["operation"] = "matrix"
    elif change == "profile":
        capture["profile"] = "driving-car"
    elif change == "retrieved_at":
        capture["retrieved_at"] = (capture_time() + timedelta(seconds=1)).isoformat()
    elif change == "response":
        capture["response"]["metadata"]["attribution"] = "TAMPERED"
        # Even a matching recomputed body hash cannot authorize a changed legacy envelope.
        capture["response_sha256"] = hashlib.sha256(canonical(capture["response"])).hexdigest()
    else:
        capture["response_sha256"] = "0" * 64
    target = tmp_path / path.name
    target.write_text(json.dumps(capture), encoding="utf-8")
    original = target.read_bytes()
    catalog = historical_catalog()
    request = DirectionsRequest(locations=[anchor.location for anchor in catalog.anchors])
    with pytest.raises(GeoError) as error:
        GeoAdapter(mode="recorded", recordings_dir=tmp_path, now=capture_time).directions(request)
    assert error.value.code in {"recording_mismatch", "recording_unavailable"}
    assert target.read_bytes() == original


@pytest.mark.parametrize("offset", [timedelta(days=2), timedelta(minutes=-6)])
def test_historical_compatibility_keeps_age_checks(
    monkeypatch: pytest.MonkeyPatch, offset: timedelta
) -> None:
    monkeypatch.setattr(httpx, "Client", no_network)
    catalog = historical_catalog()
    request = DirectionsRequest(locations=[anchor.location for anchor in catalog.anchors])
    with pytest.raises(GeoError) as error:
        GeoAdapter(
            mode="recorded", recordings_dir=RECORDINGS, now=lambda: capture_time() + offset
        ).directions(request)
    assert error.value.code == "recording_stale"


def test_historical_compatibility_does_not_override_custom_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "Client", no_network)
    catalog = historical_catalog()
    request = DirectionsRequest(locations=[anchor.location for anchor in catalog.anchors])
    with pytest.raises(GeoError) as error:
        GeoAdapter(
            mode="recorded",
            base_url="https://routing.example.test/openrouteservice",
            recordings_dir=RECORDINGS,
            now=capture_time,
        ).directions(request)
    assert error.value.code == "recording_mismatch"


def test_live_failure_does_not_use_historical_recordings() -> None:
    catalog = historical_catalog()
    request = DirectionsRequest(locations=[anchor.location for anchor in catalog.anchors])
    original = {path: path.read_bytes() for path in RECORDINGS.glob("*.json")}
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert str(request.url) == (
            "https://api.heigit.org/openrouteservice/v2/directions/foot-walking/geojson"
        )
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(GeoError) as error:
            GeoAdapter(
                api_key="SYNTHETIC-SECRET",
                client=client,
                recordings_dir=RECORDINGS,
                sleep=lambda _: None,
            ).directions(request)
    assert error.value.code == "provider_error" and error.value.status == 503
    assert len(calls) == 3
    assert {path: path.read_bytes() for path in RECORDINGS.glob("*.json")} == original


def test_offline_cli_exports_source_geometry_and_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    monkeypatch.delenv("ORS_BASE_URL", raising=False)
    monkeypatch.setattr(httpx, "Client", no_network)
    real_adapter = GeoAdapter

    def frozen_adapter(**kwargs: Any) -> GeoAdapter:
        return real_adapter(**kwargs, now=capture_time)

    monkeypatch.setattr(cli, "GeoAdapter", frozen_adapter)
    legacy_catalog_path = tmp_path / "legacy-anchors.json"
    legacy_catalog_path.write_text(historical_catalog().model_dump_json(), encoding="utf-8")
    assert (
        cli.main(
            [
                "--mode",
                "recorded",
                "--anchors",
                str(legacy_catalog_path),
                "--recordings-dir",
                str(RECORDINGS),
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    for name in ("route.geojson", "isochrones.geojson"):
        actual = json.loads((tmp_path / name).read_bytes())
        expected = json.loads((ROOT / "data/geo/demo" / name).read_bytes())
        expected["viberoute_provenance"]["mode"] = "recorded"
        assert actual == expected
    matrix = json.loads((tmp_path / "matrix.json").read_bytes())
    assert matrix["provenance"]["mode"] == "recorded"


def test_live_cli_without_key_fails_before_any_network(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    monkeypatch.setattr(httpx, "Client", no_network)
    assert cli.main(["--anchors", str(CATALOG), "--output-dir", str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "configuration_missing"
    assert not list(tmp_path.iterdir())
