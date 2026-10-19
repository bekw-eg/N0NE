"""Independent graph checks for every directed pair, without reachability claims."""

from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from itertools import permutations
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Literal

from .adapter import GeoAdapter, GeoError
from .anchors import AnchorCatalog
from .exports import atomic_json
from .models import (
    DirectionsRequest,
    GeoPoint,
    IsochronesRequest,
    IsochronesResult,
    MatrixRequest,
    MatrixResult,
    RouteResult,
)


def endpoint_offset_m(point: GeoPoint, snapped: tuple[float, float]) -> float:
    """Great-circle offset only: never an extra walking leg or entrance proof."""
    lon1, lat1, lon2, lat2 = map(radians, (point.longitude, point.latitude, snapped[0], snapped[1]))
    value = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return round(2 * 6371008.8 * asin(sqrt(min(1, value))), 2)


def run_scenario(
    catalog: AnchorCatalog,
    adapter: GeoAdapter,
    output_dir: Path,
    *,
    mode: Literal["live", "recorded"],
    snap_radius_m: float = 100.0,
) -> bool:
    """Export partial failures honestly; the manifest is the authoritative file list."""
    checks: list[dict[str, object]] = []
    points = {anchor.id: anchor.location for anchor in catalog.anchors}
    for anchor in catalog.anchors:
        points.update({point.id: point.location for point in anchor.alternative_entrances})

    def attempt(
        operation: str,
        ids: list[str],
        call: Callable[[], RouteResult | IsochronesResult | MatrixResult],
    ) -> None:
        filename = f"{len(checks):02d}-{operation}." + (
            "json" if operation == "matrix" else "geojson"
        )
        path = output_dir / filename
        check: dict[str, object] = {"operation": operation, "point_ids": ids, "mode": mode}
        try:
            result = call()
        except GeoError as exc:
            path.unlink(missing_ok=True)
            check.update(
                status="error",
                result=None,
                error={"code": exc.code, "status": exc.status, "provider_code": exc.provider_code},
            )
        else:
            if isinstance(result, MatrixResult):
                document = result.model_dump(mode="json")
            else:
                document = result.geojson.model_dump(mode="json")
                document["viberoute_provenance"] = result.provenance.model_dump(mode="json")
            atomic_json(path, document)
            check.update(
                status="ok", file=filename, provenance=result.provenance.model_dump(mode="json")
            )
            if isinstance(result, RouteResult):
                coords = result.geojson.features[0].geometry.coordinates
                check.update(
                    distance_meters=result.distance_meters,
                    duration_seconds=result.duration_seconds,
                    endpoint_offsets_m=[
                        endpoint_offset_m(points[ids[0]], coords[0]),
                        endpoint_offset_m(points[ids[-1]], coords[-1]),
                    ],
                    offset_method="great_circle_to_returned_endpoint_not_walkable_connection",
                )
        checks.append(check)

    for start, end in permutations(catalog.anchors, 2):
        request = DirectionsRequest(
            locations=[start.location, end.location], snap_radius_m=snap_radius_m
        )
        attempt("directions", [start.id, end.id], partial(adapter.directions, request))
    for anchor in catalog.anchors:
        iso_request = IsochronesRequest(origin=anchor.location)
        attempt("isochrones", [anchor.id], partial(adapter.isochrones, iso_request))
    matrix_request = MatrixRequest(locations=[anchor.location for anchor in catalog.anchors])
    attempt(
        "matrix", [anchor.id for anchor in catalog.anchors], lambda: adapter.matrix(matrix_request)
    )
    for anchor in catalog.anchors:
        entrances = [*anchor.alternative_entrances]
        if anchor.coordinate_kind == "mapped_entrance":
            entrances.insert(0, anchor)
        for entrance_start, entrance_end in permutations(entrances, 2):
            request = DirectionsRequest(
                locations=[entrance_start.location, entrance_end.location],
                snap_radius_m=snap_radius_m,
            )
            attempt(
                "directions",
                [entrance_start.id, entrance_end.id],
                partial(adapter.directions, request),
            )
    atomic_json(output_dir / "anchors.json", catalog.model_dump(mode="json"))
    success = all(check["status"] == "ok" for check in checks)
    atomic_json(
        output_dir / "manifest.json",
        {
            "mode": mode,
            "attempted_at": datetime.now(UTC).isoformat(),
            "anchor_ids": [anchor.id for anchor in catalog.anchors],
            "all_checks_succeeded": success,
            "limitations": [
                "Graph reachability and snap offsets do not verify entrance access.",
                "Opening status and wheelchair accessibility remain unknown.",
                "Only files referenced by successful checks belong to this run.",
            ],
            "checks": checks,
        },
    )
    return success
