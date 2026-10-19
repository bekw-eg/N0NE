"""Stateless H3-to-anchor matching. Never persist cells or call location providers."""

from typing import get_args

import h3
from viberoute_data.models import BoundingBox
from viberoute_geo import AnchorCatalog, GeoPoint

from app.core.config import ROOT, Settings
from app.schemas.privacy import (
    H3AnchorMatch,
    H3NoNearbyAnchor,
    H3ResolveRequest,
    H3ResolveResponse,
)
from app.schemas.routes import AnchorID
from app.services.route_planner import haversine

# Conservative MVP coverage, identical to data/astana/README.md, not city boundaries.
# Membership uses the cell center; it does not assert that the entire cell is inside.
SUPPORTED_AREA = BoundingBox(south=51.075, west=71.385, north=51.145, east=71.455)


class PrivacyService:
    def __init__(self, settings: Settings) -> None:
        catalog = AnchorCatalog.model_validate_json((ROOT / "shared/anchors.json").read_bytes())
        by_id = {anchor.id: anchor for anchor in catalog.anchors}
        self.anchors = {anchor_id: by_id[anchor_id] for anchor_id in get_args(AnchorID)}
        self.max_distance_m = settings.privacy_max_anchor_distance_m

    def resolve(self, request: H3ResolveRequest) -> H3ResolveResponse:
        # The only derived position is a coarse cell center, never a GPS input.
        latitude, longitude = h3.cell_to_latlng(request.h3_cell)
        if not SUPPORTED_AREA.contains(latitude, longitude):
            return H3NoNearbyAnchor(
                reason="outside_supported_area",
                warnings=["approximate_location", "manual_anchor_selection_required"],
            )

        center = GeoPoint(latitude=latitude, longitude=longitude)
        # ID breaks exact distance ties independently of catalog/insertion order.
        distance, anchor_id = min(
            (haversine(center, anchor.location), anchor_id)
            for anchor_id, anchor in self.anchors.items()
        )
        # Compare before rounding so a distant point cannot pass the configured limit.
        if distance > self.max_distance_m:
            return H3NoNearbyAnchor(
                reason="no_anchor_within_radius",
                warnings=["approximate_location", "manual_anchor_selection_required"],
            )
        return H3AnchorMatch(
            start_anchor_id=anchor_id,
            distance_estimate_m=round(distance),
            warnings=["approximate_location", "anchor_distance_not_walking_distance"],
        )
