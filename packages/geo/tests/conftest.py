"""SYNTHETIC provider responses for tests only; these are not real route fixtures."""

from datetime import UTC, datetime
from typing import Any

import pytest
from viberoute_geo import GeoPoint

NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)


@pytest.fixture
def points() -> list[GeoPoint]:
    return [GeoPoint(longitude=71.4, latitude=51.1), GeoPoint(longitude=71.401, latitude=51.101)]


@pytest.fixture
def route() -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "metadata": {"attribution": "SYNTHETIC TEST ONLY", "service": "routing"},
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[71.4, 51.1], [71.4005, 51.1], [71.401, 51.101]],
                },
                "properties": {
                    "summary": {"distance": 180.5, "duration": 145.2},
                    "way_points": [0, 2],
                },
            }
        ],
    }


@pytest.fixture
def isochrones() -> dict[str, Any]:
    ring = [[71.4, 51.1], [71.401, 51.1], [71.401, 51.101], [71.4, 51.1]]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {"group_index": 0, "value": value, "center": [71.4, 51.1]},
            }
            for value in (600, 900)
        ],
    }


@pytest.fixture
def matrix() -> dict[str, Any]:
    snaps = [
        {"location": point, "snapped_distance": 3.2} for point in [[71.4, 51.1], [71.401, 51.101]]
    ]
    return {
        "durations": [[0, 145.2], [160.1, 0]],
        "distances": [[0, 180.5], [195.1, 0]],
        "sources": snaps,
        "destinations": snaps,
    }
