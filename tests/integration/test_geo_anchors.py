"""Actual four-zone captures, immutable legacy data, and replay without network."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

import httpx
import pytest
from viberoute_geo import AnchorCatalog, GeoAdapter, cli
from viberoute_geo.adapter import canonical, recording_name
from viberoute_geo.models import GeoCapture, IsochronesGeoJSON, MatrixResult, RouteGeoJSON

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "data/geo/anchors"
MANIFEST = json.loads((SNAPSHOT / "demo/manifest.json").read_bytes())


def no_network(*args: Any, **kwargs: Any) -> NoReturn:
    raise AssertionError("Real capture replay must not use the network")


@pytest.mark.parametrize("check", MANIFEST["checks"], ids=lambda c: "-".join(c["point_ids"]))
def test_real_exports_have_valid_geometry_or_matrix_and_full_provenance(
    check: dict[str, Any],
) -> None:
    document = json.loads((SNAPSHOT / "demo" / check["file"]).read_bytes())
    assert check["status"] == "ok"
    if check["operation"] == "matrix":
        result = MatrixResult.model_validate(document)
        assert len(result.data.durations) == len(result.data.distances) == 4
        assert all(len(row) == 4 for row in result.data.durations + result.data.distances)
        assert result.source_indices == result.destination_indices == [0, 1, 2, 3]
        provenance = document["provenance"]
        assert all(s is not None and s.snapped_distance >= 0 for s in result.data.sources)
    else:
        provenance = document.pop("viberoute_provenance")
        if check["operation"] == "directions":
            route = RouteGeoJSON.model_validate(document)
            coords = route.features[0].geometry.coordinates
            assert len(coords) > 2 and len(set(coords)) > 2
            assert all(71.3 < lon < 71.5 and 51.0 < lat < 51.2 for lon, lat in coords)
            assert route.features[0].properties.summary.distance == check["distance_meters"]
            assert len(check["endpoint_offsets_m"]) == 2
        else:
            area = IsochronesGeoJSON.model_validate(document)
            assert [f.properties.value for f in area.features] == [600, 900]
    assert provenance["mode"] == "live"
    assert provenance["endpoint"].startswith("https://api.heigit.org/openrouteservice/v2/")
    assert provenance == check["provenance"]
    assert provenance["metadata"]["attribution"] == (
        "openrouteservice.org | OpenStreetMap contributors"
    )


def test_complete_four_zone_offline_demo_replays_identical_real_geometry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captures = {p: p.read_bytes() for p in (SNAPSHOT / "recordings").glob("*.json")}
    assert len(captures) == 19
    clock = max(GeoCapture.model_validate_json(raw).retrieved_at for raw in captures.values())
    monkeypatch.setattr(httpx, "Client", no_network)
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    monkeypatch.delenv("ORS_BASE_URL", raising=False)

    def frozen_adapter(**kwargs: Any) -> GeoAdapter:
        return GeoAdapter(**kwargs, now=lambda: clock)

    monkeypatch.setattr(cli, "GeoAdapter", frozen_adapter)
    assert (
        cli.main(
            [
                "--all-anchors",
                "--mode",
                "recorded",
                "--anchors",
                str(ROOT / "shared/anchors.json"),
                "--recordings-dir",
                str(SNAPSHOT / "recordings"),
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    actual = json.loads((tmp_path / "manifest.json").read_bytes())
    assert actual["mode"] == "recorded" and actual["all_checks_succeeded"]
    assert actual["anchor_ids"] == MANIFEST["anchor_ids"]
    for original, replay in zip(MANIFEST["checks"], actual["checks"], strict=True):
        expected = json.loads((SNAPSHOT / "demo" / original["file"]).read_bytes())
        key = "provenance" if original["operation"] == "matrix" else "viberoute_provenance"
        expected[key]["mode"] = "recorded"
        assert json.loads((tmp_path / replay["file"]).read_bytes()) == expected
        expected_check = dict(original)
        expected_check["mode"] = "recorded"
        expected_check["provenance"] = dict(original["provenance"], mode="recorded")
        assert replay == expected_check
    assert {p: p.read_bytes() for p in captures} == captures
    assert AnchorCatalog.model_validate_json((tmp_path / "anchors.json").read_bytes()) == (
        AnchorCatalog.model_validate_json((ROOT / "shared/anchors.json").read_bytes())
    )


def test_real_captures_have_matching_response_hashes_and_retrieval_dates() -> None:
    for path in (SNAPSHOT / "recordings").glob("*.json"):
        capture = GeoCapture.model_validate_json(path.read_bytes())
        assert hashlib.sha256(canonical(capture.response)).hexdigest() == capture.response_sha256
        assert path.name == recording_name(capture.operation, capture.request)
        assert capture.retrieved_at <= datetime.fromisoformat(MANIFEST["attempted_at"])
        assert capture.response.get("metadata", {}).get("attribution")


def test_all_historical_captures_and_demo_bytes_remain_unchanged() -> None:
    hashes = {
        (
            "recordings/directions-"
            "dbfd8b0e6341b3a44f06656ca10ffa24e5e96f03da4050f51af947a380bf2759.json"
        ): "3b69485ca9320faffbca8eb7f21ebeef938ccf0188569b2d730f22f42637c3fa",
        (
            "recordings/isochrones-"
            "5e71d836b993a159e7619ae99355234f11435b32fc6555387d334441fad23e68.json"
        ): "9a98c59219fe6c52c7f8918c65b15ea0b24af5b8628aa2be63f64b95dcdb1250",
        (
            "recordings/matrix-"
            "4cf7d951591702c72e666210b482ced41a887719664ed81081bbe6939a5502b4.json"
        ): "ffcc6ee1d935cc11cc53018051217f8bad3fc83a63bafac4cc893346ffdf15ad",
        "demo/anchors.json": "b3df45e9fa060e229c079d6890f6c2ef357a08de14239bf1e8ccceabbd88fd48",
        "demo/isochrones.geojson": (
            "2f44606ca496053a64b32729a602f1198f030950692f59762c49e31f75995f73"
        ),
        "demo/matrix.json": "6618c247dd985adbc960ecec2d6decf0502c94a2c5cc1e6ff71136d2eb47ca96",
        "demo/route.geojson": "cd5cd994d95ff13a9ab3c59a58873d5489fca3a7c1b7eac625d97ecdbb7b0176",
    }
    for relative, expected in hashes.items():
        assert hashlib.sha256((ROOT / "data/geo" / relative).read_bytes()).hexdigest() == expected
