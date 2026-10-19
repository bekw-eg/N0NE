import copy
import json

import pytest
from pydantic import ValidationError

from viberoute_data.models import BoundingBox, Capture, Dataset
from viberoute_data.normalize import capture_bytes, geojson, normalize, validate_source
from viberoute_data.overpass import CollectionError


def with_elements(capture: Capture, elements: list[dict[str, object]]) -> Capture:
    document = capture.model_dump(mode="json")
    document["response"]["elements"] = elements
    return Capture.model_validate(document)


def test_unknown_attributes_and_hours_are_not_fabricated(capture: Capture) -> None:
    dataset = normalize(capture)
    poi = dataset.pois[0]
    assert poi.attributes.indoor is None
    assert poi.attributes.covered is None
    assert poi.opening_hours is None
    assert poi.name == "SYNTHETIC TEST CAFE"
    assert "indoor_unknown" in poi.quality_warnings
    assert "opening_hours" not in poi.provenance.field_tags
    assert poi.provenance.osm_updated_at != poi.provenance.retrieved_at
    assert poi.provenance.field_tags["category"] == ["amenity"]


def test_explicit_fields_keep_tag_evidence(capture: Capture, element: dict[str, object]) -> None:
    element["tags"] = {
        "amenity": "cafe",
        "name:kk": "SYNTHETIC TEST NAME",
        "indoor": "yes",
        "covered": "no",
        "wheelchair": "limited",
        "opening_hours": "Mo-Fr 10:00-18:00",
        "addr:street": "SYNTHETIC TEST STREET",
        "addr:housenumber": "1",
    }
    poi = normalize(with_elements(capture, [element])).pois[0]
    assert poi.attributes.indoor is True
    assert poi.attributes.covered is False
    assert poi.attributes.wheelchair == "limited"
    assert poi.opening_hours == "Mo-Fr 10:00-18:00"
    assert poi.address["street"] == "SYNTHETIC TEST STREET"
    assert poi.provenance.field_tags["name"] == ["name:kk"]
    assert poi.provenance.field_tags["attributes.indoor"] == ["indoor"]


def test_way_center_is_not_an_entrance(capture: Capture, element: dict[str, object]) -> None:
    element.update(type="way", center={"lat": 51.1, "lon": 71.42})
    element.pop("lat")
    element.pop("lon")
    dataset = normalize(with_elements(capture, [element]))
    poi = dataset.pois[0]
    assert poi.coordinates.kind == "bounding_box_center"
    assert "location_is_bbox_center_not_entrance" in poi.quality_warnings
    feature = geojson(dataset)["features"][0]
    assert feature["geometry"]["coordinates"] == [71.42, 51.1]
    assert feature["properties"]["coordinate_kind"] == "bounding_box_center"


def test_identical_duplicate_ids_are_deduplicated(
    capture: Capture, element: dict[str, object]
) -> None:
    dataset = normalize(with_elements(capture, [element, copy.deepcopy(element)]))
    assert len(dataset.pois) == 1
    assert dataset.stats.duplicate_elements == 1
    assert dataset.stats.input_elements == 2


def test_conflicting_duplicate_evidence_rejected(
    capture: Capture, element: dict[str, object]
) -> None:
    other = copy.deepcopy(element)
    other["tags"] = {"amenity": "cafe", "indoor": "yes"}
    with pytest.raises(CollectionError, match="Conflicting duplicate"):
        normalize(with_elements(capture, [element, other]))


def test_same_name_different_osm_objects_are_preserved(
    capture: Capture, element: dict[str, object]
) -> None:
    other = copy.deepcopy(element)
    other["id"] = 101
    assert len(normalize(with_elements(capture, [element, other])).pois) == 2


@pytest.mark.parametrize(
    "tags",
    [
        {"amenity": "cafe", "access": "private"},
        {"amenity": "cafe", "access": "no"},
        {"amenity": "cafe", "disused": "yes"},
        {"amenity": "cafe", "abandoned": "yes"},
        {"amenity": "parking"},
    ],
)
def test_ineligible_objects_excluded(
    capture: Capture,
    element: dict[str, object],
    tags: dict[str, str],
) -> None:
    element["tags"] = tags
    dataset = normalize(with_elements(capture, [element]))
    assert not dataset.pois
    assert dataset.stats.skipped_elements == 1


@pytest.mark.parametrize("change", [{"lat": 52.0}, {"type": "way"}])
def test_outside_or_missing_geometry_skipped(
    capture: Capture,
    element: dict[str, object],
    change: dict[str, object],
) -> None:
    element.update(change)
    assert not normalize(with_elements(capture, [element])).pois


def test_unnamed_playground_has_null_name(capture: Capture, element: dict[str, object]) -> None:
    element["tags"] = {"leisure": "playground"}
    poi = normalize(with_elements(capture, [element])).pois[0]
    assert poi.name is None
    assert "missing_name" in poi.quality_warnings


@pytest.mark.parametrize("coordinates", [{"lat": 91.0}, {"lon": -181.0}])
def test_invalid_coordinates_fail(
    capture: Capture,
    element: dict[str, object],
    coordinates: dict[str, float],
) -> None:
    element.update(coordinates)
    with pytest.raises(CollectionError, match="Invalid OSM coordinates"):
        normalize(with_elements(capture, [element]))


def test_capture_replay_and_tampered_facts(capture: Capture) -> None:
    raw = capture_bytes(capture)
    dataset = normalize(capture, raw_bytes=raw)
    validate_source(dataset, raw)
    document = dataset.model_dump(mode="json")
    document["pois"][0]["name"] = "TAMPERED FAKE NAME"
    with pytest.raises(ValueError, match="differs"):
        validate_source(Dataset.model_validate(document), raw)
    with pytest.raises(ValueError, match="SHA-256"):
        validate_source(dataset, raw + b" ")


def test_source_url_cannot_refer_to_another_poi(capture: Capture) -> None:
    document = normalize(capture).model_dump(mode="json")
    document["pois"][0]["provenance"]["url"] = "https://www.openstreetmap.org/node/999"
    with pytest.raises(ValidationError, match="identity"):
        Dataset.model_validate(document)


def test_schema_and_counts_are_enforced(capture: Capture) -> None:
    document = normalize(capture).model_dump(mode="json")
    document["stats"]["input_elements"] = 900
    with pytest.raises(ValidationError, match="counts"):
        Dataset.model_validate(document)
    assert Dataset.model_json_schema()["additionalProperties"] is False


@pytest.mark.parametrize("field,value", [("lat", float("nan")), ("lon", float("inf"))])
def test_nonfinite_capture_rejected(
    capture: Capture,
    element: dict[str, object],
    field: str,
    value: float,
) -> None:
    element[field] = value
    with pytest.raises(ValidationError, match="Non-finite"):
        with_elements(capture, [element])


def test_bbox_requires_correct_order() -> None:
    with pytest.raises(ValidationError, match="south < north"):
        BoundingBox(south=52, north=51, west=71, east=72)


@pytest.mark.parametrize("bad_identity", [{"type": []}, {"id": True}, {"id": -1}])
def test_malformed_identities_fail_cleanly(
    capture: Capture,
    element: dict[str, object],
    bad_identity: dict[str, object],
) -> None:
    element.update(bad_identity)
    with pytest.raises(CollectionError, match="identity"):
        normalize(with_elements(capture, [element]))


def test_captured_json_is_utf8_and_stable(capture: Capture) -> None:
    raw = capture_bytes(capture)
    assert capture_bytes(Capture.model_validate_json(raw)) == raw
    assert json.loads(raw)["format_version"] == "1"
