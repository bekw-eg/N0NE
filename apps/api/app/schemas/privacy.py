"""Location-sensitive, cell-only input and minimal anchor resolution output."""

from typing import Annotated, Literal

import h3
from pydantic import ConfigDict, Field, field_validator

from app.schemas.poi import Model
from app.schemas.routes import AnchorID

H3_RESOLUTION: Literal[8] = 8
PrivacyWarning = Literal[
    "approximate_location",
    "anchor_distance_not_walking_distance",
    "manual_anchor_selection_required",
]


class H3ResolveRequest(Model):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    h3_cell: str = Field(
        strict=True,
        min_length=15,
        max_length=15,
        pattern=r"^[0-9a-fA-F]{15}$",
        repr=False,
        description="Sensitive H3 cell index, resolution 8; generated on the device only.",
    )

    @field_validator("h3_cell")
    @classmethod
    def valid_cell(cls, value: str) -> str:
        if not h3.is_valid_cell(value):
            raise ValueError("A valid H3 cell is required")
        if h3.get_resolution(value) != H3_RESOLUTION:
            raise ValueError("H3 resolution must be exactly 8")
        return value


class H3AnchorMatch(Model):
    status: Literal["matched"] = "matched"
    start_anchor_id: AnchorID
    resolution: Literal[8] = H3_RESOLUTION
    distance_estimate_m: int = Field(
        ge=0,
        strict=True,
        description="Approximate straight-line meters from the H3 cell center to the anchor; "
        "not walking distance, time, or distance from the user's GPS position.",
    )
    warnings: list[PrivacyWarning]


class H3NoNearbyAnchor(Model):
    status: Literal["no_nearby_anchor"] = "no_nearby_anchor"
    reason: Literal["outside_supported_area", "no_anchor_within_radius"]
    resolution: Literal[8] = H3_RESOLUTION
    warnings: list[PrivacyWarning]


H3ResolveResponse = Annotated[H3AnchorMatch | H3NoNearbyAnchor, Field(discriminator="status")]
