"""Opt-in provider smoke test using a public landmark catalog, never GPS input."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, Field, HttpUrl, ValidationError

from .adapter import DEFAULT_BASE_URL, GeoAdapter, GeoError
from .models import (
    DirectionsRequest,
    GeoPoint,
    IsochronesRequest,
    MatrixRequest,
    Model,
)


class Anchor(Model):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    location: GeoPoint
    coordinate_kind: Literal["osm_node", "bounding_box_center", "mapped_entrance"]
    source_url: HttpUrl
    osm_version: int = Field(gt=0, strict=True)
    osm_updated_at: AwareDatetime
    retrieved_at: AwareDatetime


class AnchorCatalog(Model):
    schema_version: Literal["0.1.0"]
    description: str
    anchors: list[Anchor]


def atomic_json(path: Path, value: object) -> None:
    contents = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(contents)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ORS walking smoke test for public anchors")
    parser.add_argument("--anchors", type=Path, default=Path("shared/anchors.json"))
    parser.add_argument("--origin", default="mega_silk_way")
    parser.add_argument("--destination", default="botanical_garden")
    parser.add_argument("--mode", choices=("live", "recorded"), default="live")
    parser.add_argument("--recordings-dir", type=Path, default=Path("data/geo/recordings"))
    parser.add_argument("--max-recording-age-seconds", type=int, default=86400)
    parser.add_argument("--snap-radius-m", type=float, default=100)
    parser.add_argument("--output-dir", type=Path, default=Path("data/geo/demo"))
    args = parser.parse_args(argv)
    try:
        catalog = AnchorCatalog.model_validate_json(args.anchors.read_bytes())
        by_id = {anchor.id: anchor for anchor in catalog.anchors}
        if len(by_id) != len(catalog.anchors):
            raise ValueError("Anchor IDs must be unique")
        origin, destination = by_id[args.origin], by_id[args.destination]
        adapter = GeoAdapter(
            api_key=os.environ.get("ORS_API_KEY"),
            base_url=os.environ.get("ORS_BASE_URL", DEFAULT_BASE_URL),
            mode=args.mode,
            recordings_dir=args.recordings_dir,
            max_recording_age_seconds=args.max_recording_age_seconds,
        )
        locations = [origin.location, destination.location]
        route = adapter.directions(
            DirectionsRequest(locations=locations, snap_radius_m=args.snap_radius_m)
        )
        isochrones = adapter.isochrones(IsochronesRequest(origin=origin.location))
        matrix = adapter.matrix(MatrixRequest(locations=locations))
        # Publish demo output only after all three operations have succeeded.
        route_geojson = route.geojson.model_dump(mode="json")
        route_geojson["viberoute_provenance"] = route.provenance.model_dump(mode="json")
        isochrone_geojson = isochrones.geojson.model_dump(mode="json")
        isochrone_geojson["viberoute_provenance"] = isochrones.provenance.model_dump(mode="json")
        atomic_json(args.output_dir / "route.geojson", route_geojson)
        atomic_json(args.output_dir / "isochrones.geojson", isochrone_geojson)
        atomic_json(args.output_dir / "matrix.json", matrix.model_dump(mode="json"))
        atomic_json(
            args.output_dir / "anchors.json",
            {
                "origin": origin.model_dump(mode="json"),
                "destination": destination.model_dump(mode="json"),
            },
        )
        print(
            json.dumps(
                {
                    "mode": route.provenance.mode,
                    "duration_seconds": route.duration_seconds,
                    "distance_meters": route.distance_meters,
                    "isochrone_ranges_seconds": [600, 900],
                }
            )
        )
        return 0
    except GeoError as exc:
        print(
            json.dumps(
                {
                    "error": exc.code,
                    "message": str(exc),
                    "status": exc.status,
                    "provider_code": exc.provider_code,
                }
            ),
            file=sys.stderr,
        )
        return 2
    except (ValueError, ValidationError, OSError, KeyError):
        print(
            json.dumps(
                {"error": "invalid_input", "message": "Check anchor catalog, IDs, and settings"}
            ),
            file=sys.stderr,
        )
        return 2
