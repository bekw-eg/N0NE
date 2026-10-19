"""Deterministic normalization without inferred amenities or opening hours."""

import hashlib
import json
from datetime import datetime
from typing import Literal, cast

from pydantic import AwareDatetime, TypeAdapter, ValidationError

from .models import POI, Attributes, Capture, CollectionStats, Coordinates, Dataset, Provenance
from .overpass import CATEGORY_VALUES, CollectionError, check_response

TAG_KEYS = {
    "name",
    "name:ru",
    "name:kk",
    "name:en",
    "opening_hours",
    "indoor",
    "covered",
    "wheelchair",
    "amenity",
    "tourism",
    "leisure",
    "shop",
    "access",
    "disused",
    "abandoned",
    "check_date",
    "check_date:opening_hours",
    "website",
    "contact:website",
    "wikidata",
}
OSM_TYPES = {"node", "way", "relation"}
TIME_ADAPTER = TypeAdapter(AwareDatetime)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def capture_bytes(capture: Capture) -> bytes:
    return json_bytes(capture.model_dump(mode="json"))


def _deduplicate(elements: list[dict[str, object]]) -> tuple[list[dict[str, object]], int]:
    by_id: dict[tuple[str, int], dict[str, object]] = {}
    duplicates = 0
    for element in elements:
        kind, osm_id = element.get("type"), element.get("id")
        if (
            not isinstance(kind, str)
            or kind not in OSM_TYPES
            or type(osm_id) is not int
            or osm_id <= 0
        ):
            raise CollectionError("Invalid OSM element identity")
        key = (str(kind), osm_id)
        if key in by_id:
            duplicates += 1
            previous = by_id[key]
            # Do not silently combine contradictory evidence from overlapping queries.
            if previous != element:
                raise CollectionError(f"Conflicting duplicate OSM element: {key}")
        else:
            by_id[key] = element
    return [by_id[key] for key in sorted(by_id)], duplicates


def _normalize(element: dict[str, object], capture: Capture) -> POI | None:
    raw_tags = element.get("tags", {})
    if not isinstance(raw_tags, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in raw_tags.items()
    ):
        raise CollectionError("OSM tags must be string-to-string mappings")
    tags = {
        key: value
        for key, value in raw_tags.items()
        if (key in TAG_KEYS or key.startswith("addr:")) and value.strip()
    }
    if tags.get("access") in {"no", "private"}:
        return None
    if tags.get("disused") == "yes" or tags.get("abandoned") == "yes":
        return None
    category_key = next(
        (key for key, values in CATEGORY_VALUES.items() if tags.get(key) in values), None
    )
    if category_key is None:
        return None
    kind = cast(Literal["node", "way", "relation"], element["type"])
    point = element if kind == "node" else element.get("center")
    if not isinstance(point, dict) or "lat" not in point or "lon" not in point:
        return None
    try:
        coordinates = Coordinates(
            latitude=point["lat"],
            longitude=point["lon"],
            kind="osm_node" if kind == "node" else "bounding_box_center",
        )
    except ValidationError as exc:
        raise CollectionError("Invalid OSM coordinates") from exc
    if not capture.bbox.contains(coordinates.latitude, coordinates.longitude):
        return None
    name_key = next((key for key in ("name", "name:ru", "name:kk", "name:en") if key in tags), None)
    field_tags = {"category": [category_key]}
    if name_key:
        field_tags["name"] = [name_key]
    address = {key[5:]: value for key, value in tags.items() if key.startswith("addr:")}
    for key in address:
        field_tags[f"address.{key}"] = [f"addr:{key}"]
    if "opening_hours" in tags:
        field_tags["opening_hours"] = ["opening_hours"]
    attributes = Attributes()
    for key in ("indoor", "covered"):
        if tags.get(key) in {"yes", "no"}:
            setattr(attributes, key, tags[key] == "yes")
            field_tags[f"attributes.{key}"] = [key]
    if tags.get("wheelchair") in {"yes", "no", "limited"}:
        attributes.wheelchair = cast(Literal["yes", "no", "limited"], tags["wheelchair"])
        field_tags["attributes.wheelchair"] = ["wheelchair"]
    warnings = []
    if name_key is None:
        warnings.append("missing_name")
    if "opening_hours" not in tags:
        warnings.append("missing_opening_hours")
    if attributes.indoor is None:
        warnings.append("indoor_unknown")
    if coordinates.kind == "bounding_box_center":
        warnings.append("location_is_bbox_center_not_entrance")
    if element.get("timestamp") is None:
        warnings.append("missing_osm_update_timestamp")
    source = Provenance.model_validate(
        {
            "url": f"https://www.openstreetmap.org/{kind}/{element['id']}",
            "element_type": kind,
            "element_id": element["id"],
            "osm_version": element.get("version"),
            "osm_updated_at": element.get("timestamp"),
            "retrieved_at": capture.retrieved_at,
            "field_tags": field_tags,
        }
    )
    return POI.model_validate(
        {
            "id": f"osm:{kind}:{element['id']}",
            "name": tags[name_key] if name_key else None,
            "category": tags[category_key],
            "coordinates": coordinates,
            "address": address,
            "opening_hours": tags.get("opening_hours"),
            "attributes": attributes,
            "tags": tags,
            "provenance": source,
            "quality_warnings": warnings,
        }
    )


def normalize(capture: Capture, *, raw_bytes: bytes | None = None) -> Dataset:
    payload = check_response(capture.response)
    elements = cast(list[dict[str, object]], payload["elements"])
    unique, duplicates = _deduplicate(elements)
    pois = [poi for item in unique if (poi := _normalize(item, capture)) is not None]
    metadata = payload.get("osm3s", {})
    base_timestamp: datetime | None = None
    if isinstance(metadata, dict) and metadata.get("timestamp_osm_base"):
        base_timestamp = TIME_ADAPTER.validate_python(metadata["timestamp_osm_base"])
    return Dataset(
        collected_at=capture.retrieved_at,
        osm_base_timestamp=base_timestamp,
        endpoint=capture.endpoint,
        bbox=capture.bbox,
        query=capture.query,
        raw_sha256=hashlib.sha256(
            raw_bytes if raw_bytes is not None else capture_bytes(capture)
        ).hexdigest(),
        stats=CollectionStats(
            input_elements=len(elements),
            duplicate_elements=duplicates,
            skipped_elements=len(unique) - len(pois),
            output_pois=len(pois),
        ),
        pois=pois,
    )


def geojson(dataset: Dataset) -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "attribution": dataset.attribution,
        "license": dataset.license,
        "features": [
            {
                "type": "Feature",
                "id": poi.id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [poi.coordinates.longitude, poi.coordinates.latitude],
                },
                "properties": poi.model_dump(mode="json", exclude={"coordinates"})
                | {
                    "coordinate_kind": poi.coordinates.kind,
                },
            }
            for poi in dataset.pois
        ],
    }


def validate_source(dataset: Dataset, raw: bytes) -> None:
    """Rebuild from the recorded source; reject altered facts or mismatched captures."""
    if hashlib.sha256(raw).hexdigest() != dataset.raw_sha256:
        raise ValueError("Raw capture SHA-256 does not match dataset")
    capture = Capture.model_validate_json(raw)
    rebuilt = normalize(capture, raw_bytes=raw)
    if rebuilt != dataset:
        raise ValueError("Dataset differs from deterministic source normalization")
