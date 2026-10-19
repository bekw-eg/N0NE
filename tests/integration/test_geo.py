"""Offline integration against actual ORS captures, not synthetic geometry."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

import httpx
import pytest
from viberoute_geo import cli
from viberoute_geo.models import GeoCapture

from apps.api.app.integrations.geo_adapter import (
    DirectionsRequest,
    GeoAdapter,
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


def no_network(*args: Any, **kwargs: Any) -> NoReturn:
    raise AssertionError("Offline integration must not open an HTTP client")


def test_backend_facade_replays_all_real_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "Client", no_network)
    catalog = cli.AnchorCatalog.model_validate_json(CATALOG.read_bytes())
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
    assert (
        cli.main(
            [
                "--mode",
                "recorded",
                "--anchors",
                str(CATALOG),
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
