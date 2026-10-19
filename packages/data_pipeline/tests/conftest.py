"""All objects in these unit fixtures are SYNTHETIC, not real establishments."""

from datetime import UTC, datetime

import pytest

from viberoute_data.models import BoundingBox, Capture
from viberoute_data.overpass import DEFAULT_ENDPOINT, build_query


@pytest.fixture
def element() -> dict[str, object]:
    return {
        "type": "node",
        "id": 100,
        "lat": 51.1,
        "lon": 71.42,
        "version": 3,
        "timestamp": "2025-01-01T00:00:00Z",
        "tags": {"name": "SYNTHETIC TEST CAFE", "amenity": "cafe"},
    }


@pytest.fixture
def capture(element: dict[str, object]) -> Capture:
    bbox = BoundingBox(south=51.075, west=71.385, north=51.145, east=71.455)
    return Capture(
        endpoint=DEFAULT_ENDPOINT,
        bbox=bbox,
        query=build_query(bbox),
        retrieved_at=datetime(2026, 10, 19, tzinfo=UTC),
        response={
            "osm3s": {"timestamp_osm_base": "2026-10-18T23:59:00Z"},
            "elements": [element],
        },
    )
