"""Catalog evidence, conservative legacy migration, and rejected entrance claims."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from viberoute_geo import Anchor, AnchorCatalog, cli

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "shared/anchors.json"
SOURCE_KEYS = ["mega", "botanical", "expo", "nurzhol"]


def catalog() -> AnchorCatalog:
    return AnchorCatalog.model_validate_json(CATALOG.read_bytes())


def test_four_unique_stable_ids_and_public_import_compatibility() -> None:
    assert [a.id for a in catalog().anchors] == [
        "mega_silk_way",
        "botanical_garden",
        "expo_nur_alem",
        "nurzhol_boulevard",
    ]
    assert cli.Anchor is Anchor and cli.AnchorCatalog is AnchorCatalog


@pytest.mark.parametrize("index", range(4))
def test_each_coordinate_and_metadata_reproduce_from_osm_evidence(index: int) -> None:
    anchor = catalog().anchors[index]
    source = json.loads((ROOT / f"data/geo/anchors/sources/{SOURCE_KEYS[index]}.json").read_bytes())
    elements = source["response"]["elements"]
    for point in [anchor, *anchor.alternative_entrances]:
        kind, object_id = str(point.source_url).rstrip("/").rsplit("/", 2)[-2:]
        element = next(e for e in elements if e["type"] == kind and e["id"] == int(object_id))
        assert point.osm_version == element["version"]
        assert point.osm_updated_at.isoformat().replace("+00:00", "Z") == element["timestamp"]
        assert point.retrieved_at.isoformat() == source["retrieved_at"]
        assert point.osm_tags == element.get("tags", {})
        assert point.verification_status == "source_verified"
        assert point.limitations
        if point.coordinate_kind == "bounding_box_center":
            nodes = {e["id"]: e for e in elements if e["type"] == "node"}
            coords = [nodes[n] for n in element["nodes"]]
            expected = [
                round((min(n[axis] for n in coords) + max(n[axis] for n in coords)) / 2, 7)
                for axis in ("lon", "lat")
            ]
            assert point.entrance_status == "unknown"
        else:
            expected = [element["lon"], element["lat"]]
        assert point.location.ors() == expected
        # Catches a valid-in-WGS84, but reversed, Astana lat/lon pair.
        assert 71.3 < point.location.longitude < 71.5
        assert 51.0 < point.location.latitude < 51.2
        assert point.accessibility_status == point.opening_status == "unknown"
        if point.coordinate_kind == "mapped_entrance":
            way = next(e for e in elements if e["type"] == "way" and e["id"] == 499328514)
            assert element["id"] in way["nodes"]
            assert element["tags"]["entrance"] == "main"
            assert str(point.landmark_source_url).endswith("/way/499328514")
    assert source["license_url"] == "https://www.openstreetmap.org/copyright"
    assert source["attribution"] == "OpenStreetMap contributors"


def test_legacy_catalog_migrates_with_unknown_defaults_without_changing_source() -> None:
    original = json.loads((ROOT / "data/geo/demo/anchors.json").read_bytes())
    old = {"schema_version": "0.1.0", "description": "Legacy", "anchors": list(original.values())}
    migrated = AnchorCatalog.model_validate(old)
    for point, raw in zip(migrated.anchors, original.values(), strict=True):
        for key, value in raw.items():
            assert point.model_dump(mode="json")[key] == value
        assert point.verification_status == point.entrance_status == "unknown"
        assert point.alternative_entrances == []
    assert AnchorCatalog.model_validate_json(migrated.model_dump_json()) == migrated


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("coordinate_kind", "bounding_box_center"),
        ("entrance_status", "unknown"),
        ("verification_status", "unknown"),
        ("osm_tags", {}),
        ("osm_tags", {"entrance": "no"}),
        ("osm_tags", {"entrance": "exit"}),
        ("osm_tags", {"entrance": "service"}),
        ("source_url", "https://www.openstreetmap.org/way/499328514"),
        ("source_url", "https://example.com/node/13404024647"),
        ("source_url", "https://www.openstreetmap.org/node/not-an-id"),
        ("source_url", "https://www.openstreetmap.org/node/13404024647?token=unsafe"),
        ("landmark_source_url", None),
        ("landmark_source_url", "https://example.com/way/499328514"),
        ("osm_version", 0),
        ("osm_updated_at", "2099-01-01T00:00:00Z"),
        ("retrieved_at", "2026-10-19T12:00:00"),
        ("accessibility_status", "verified"),
        ("opening_status", "open"),
    ],
)
def test_unsupported_claims_and_metadata_rejected(field: str, value: Any) -> None:
    raw = catalog().anchors[0].model_dump(mode="json")
    raw[field] = value
    with pytest.raises(ValidationError):
        Anchor.model_validate(raw)


@pytest.mark.parametrize("alternative", [False, True])
def test_duplicate_ids_rejected(alternative: bool) -> None:
    raw = catalog().model_dump(mode="json")
    if alternative:
        raw["anchors"][0]["alternative_entrances"][0]["id"] = raw["anchors"][1]["id"]
    else:
        raw["anchors"][1]["id"] = raw["anchors"][0]["id"]
    with pytest.raises(ValidationError):
        AnchorCatalog.model_validate(raw)


def test_unknown_representative_node_cannot_be_promoted_to_entrance() -> None:
    raw = catalog().anchors[3].model_dump(mode="json")
    raw["coordinate_kind"] = "mapped_entrance"
    with pytest.raises(ValidationError):
        Anchor.model_validate(raw)


def test_alternative_entrance_must_belong_to_the_same_landmark() -> None:
    raw = catalog().anchors[0].model_dump(mode="json")
    raw["alternative_entrances"][0]["landmark_source_url"] = (
        "https://www.openstreetmap.org/way/1196402246"
    )
    with pytest.raises(ValidationError):
        Anchor.model_validate(raw)
