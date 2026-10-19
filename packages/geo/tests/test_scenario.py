"""SYNTHETIC responses in temporary directories only; no provider captures here."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest
from conftest import NOW
from viberoute_geo import AnchorCatalog, GeoAdapter, GeoError, MatrixRequest, cli
from viberoute_geo.scenario import endpoint_offset_m, run_scenario

ROOT = Path(__file__).resolve().parents[3]


def catalog() -> AnchorCatalog:
    return AnchorCatalog.model_validate_json((ROOT / "shared/anchors.json").read_bytes())


def synthetic_matrix() -> dict[str, Any]:
    points = [a.location.ors() for a in catalog().anchors]
    metrics = [
        [0 if i == j else (None if (i, j) == (1, 3) else 100) for j in range(4)] for i in range(4)
    ]
    return {
        "durations": metrics,
        "distances": deepcopy(metrics),
        "sources": [{"location": p, "snapped_distance": 2} for p in points],
        "destinations": [{"location": p, "snapped_distance": 3} for p in points],
        "metadata": {"attribution": "SYNTHETIC TEST ONLY"},
    }


def test_four_by_four_matrix_preserves_order_nulls_and_provenance(tmp_path: Path) -> None:
    request = MatrixRequest(locations=[a.location for a in catalog().anchors])
    document = synthetic_matrix()

    def handle(call: httpx.Request) -> httpx.Response:
        assert json.loads(call.content) == request.payload()
        assert request.payload()["sources"] == ["0", "1", "2", "3"]
        return httpx.Response(200, json=document)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = GeoAdapter(
            api_key="SYNTHETIC-SECRET", client=client, recordings_dir=tmp_path
        ).matrix(request)
    assert result.data.durations[1][3] is None and result.data.distances[1][3] is None
    assert result.data.durations[3][1] == 100  # Never assume symmetry.
    assert result.source_indices == result.destination_indices == [0, 1, 2, 3]
    assert result.provenance.metadata == document["metadata"]


@pytest.mark.parametrize("change", ["rows", "columns", "snaps", "nulls"])
def test_invalid_four_by_four_matrix_is_never_recorded(tmp_path: Path, change: str) -> None:
    document = synthetic_matrix()
    if change == "rows":
        document["distances"].pop()
    elif change == "columns":
        document["durations"][0].pop()
    elif change == "snaps":
        document["sources"].pop()
    else:
        document["durations"][1][3] = 10
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=document))
    ) as c:
        with pytest.raises(GeoError, match="dimensions or metrics"):
            GeoAdapter(api_key="TEST", client=c, recordings_dir=tmp_path).matrix(
                MatrixRequest(locations=[a.location for a in catalog().anchors])
            )
    assert not list(tmp_path.iterdir())


def test_scenario_continues_independent_checks_and_exports_no_failed_route(tmp_path: Path) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        payload = json.loads(request.content)
        if "/directions/" in str(request.url):
            return httpx.Response(404, json={"error": {"code": 2010}})
        if "/matrix/" in str(request.url):
            return httpx.Response(200, json=synthetic_matrix())
        lon, lat = payload["locations"][0]
        ring = [[lon, lat], [lon + 0.001, lat], [lon + 0.001, lat + 0.001], [lon, lat]]
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": [ring]},
                        "properties": {"group_index": 0, "value": t, "center": [lon, lat]},
                    }
                    for t in (600, 900)
                ],
                "metadata": {"attribution": "SYNTHETIC TEST ONLY"},
            },
        )

    stale = tmp_path / "00-directions.geojson"
    stale.write_text("STALE", encoding="utf-8")
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert not run_scenario(
            catalog(),
            GeoAdapter(api_key="TEST", client=client, now=lambda: NOW),
            tmp_path,
            mode="live",
        )
    manifest = json.loads((tmp_path / "manifest.json").read_bytes())
    assert len(calls) == len(manifest["checks"]) == 19
    failed = [c for c in manifest["checks"] if c["status"] == "error"]
    assert len(failed) == 14 and not stale.exists()
    assert all(c["result"] is None and "file" not in c for c in failed)
    assert all(
        c["error"] == {"code": "provider_error", "status": 404, "provider_code": 2010}
        for c in failed
    )
    matrix = next(c for c in manifest["checks"] if c["operation"] == "matrix")
    assert matrix["point_ids"] == [a.id for a in catalog().anchors]
    assert matrix["status"] == "ok"
    assert len(list(tmp_path.glob("*.geojson"))) == 4


def test_recorded_scenario_missing_captures_fails_without_network(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def no_network(**kwargs: Any) -> None:
        raise AssertionError("Offline checks must not open a client")

    monkeypatch.setattr(httpx, "Client", no_network)
    assert (
        cli.main(
            [
                "--all-anchors",
                "--mode",
                "recorded",
                "--anchors",
                str(ROOT / "shared/anchors.json"),
                "--recordings-dir",
                str(tmp_path / "empty"),
                "--output-dir",
                str(tmp_path / "output"),
            ]
        )
        == 2
    )
    manifest = json.loads((tmp_path / "output/manifest.json").read_bytes())
    assert all(c["error"]["code"] == "recording_unavailable" for c in manifest["checks"])
    assert not list((tmp_path / "output").glob("*.geojson"))


def test_endpoint_offset_is_spatial_offset_only() -> None:
    point = catalog().anchors[0].location
    assert endpoint_offset_m(point, (point.longitude, point.latitude)) == 0
    assert 69 < endpoint_offset_m(point, (point.longitude + 0.001, point.latitude)) < 71


def test_single_pair_defaults_keep_new_captures_out_of_historical_directories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def check_directory(**kwargs: Any) -> GeoAdapter:
        assert kwargs["recordings_dir"] == Path("data/tmp/geo-smoke/recordings")
        raise GeoError("configuration_missing", "Synthetic constructor failure before any writes")

    monkeypatch.setattr(cli, "GeoAdapter", check_directory)
    assert cli.main(["--anchors", str(ROOT / "shared/anchors.json")]) == 2
