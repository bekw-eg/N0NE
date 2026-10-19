"""Opt-in provider smoke test using a public landmark catalog, never GPS input."""

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from .adapter import DEFAULT_BASE_URL, GeoAdapter, GeoError
from .anchors import Anchor as Anchor
from .anchors import AnchorCatalog as AnchorCatalog
from .exports import atomic_json as atomic_json
from .models import (
    DirectionsRequest,
    IsochronesRequest,
    MatrixRequest,
)
from .scenario import run_scenario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ORS walking smoke test for public anchors")
    parser.add_argument("--anchors", type=Path, default=Path("shared/anchors.json"))
    parser.add_argument("--origin", default="mega_silk_way")
    parser.add_argument("--destination", default="botanical_garden")
    parser.add_argument(
        "--all-anchors", action="store_true", help="Check all directed anchor pairs"
    )
    parser.add_argument("--mode", choices=("live", "recorded"), default="live")
    parser.add_argument("--recordings-dir", type=Path)
    parser.add_argument("--max-recording-age-seconds", type=int, default=86400)
    parser.add_argument("--snap-radius-m", type=float, default=100)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    default_root = Path("data/geo/anchors" if args.all_anchors else "data/tmp/geo-smoke")
    args.recordings_dir = args.recordings_dir or default_root / "recordings"
    args.output_dir = args.output_dir or default_root / "demo"
    try:
        catalog = AnchorCatalog.model_validate_json(args.anchors.read_bytes())
        by_id = {anchor.id: anchor for anchor in catalog.anchors}
        if len(by_id) != len(catalog.anchors):
            raise ValueError("Anchor IDs must be unique")
        adapter = GeoAdapter(
            api_key=os.environ.get("ORS_API_KEY"),
            base_url=os.environ.get("ORS_BASE_URL", DEFAULT_BASE_URL),
            mode=args.mode,
            recordings_dir=args.recordings_dir,
            max_recording_age_seconds=args.max_recording_age_seconds,
        )
        if args.all_anchors:
            success = run_scenario(
                catalog,
                adapter,
                args.output_dir,
                mode=args.mode,
                snap_radius_m=args.snap_radius_m,
            )
            print(json.dumps({"mode": args.mode, "all_checks_succeeded": success}))
            return 0 if success else 2
        origin, destination = by_id[args.origin], by_id[args.destination]
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
