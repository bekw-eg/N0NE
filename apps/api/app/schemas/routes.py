"""Anchor-only planning contract; a failed plan cannot contain a route."""

from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator
from viberoute_geo import Anchor
from viberoute_geo.models import GeoProvenance, RouteGeoJSON

from app.schemas.poi import DatasetMetadata, Model, PublicPOI
from app.schemas.rag import Language, RetrievalMode

AnchorID = Literal["mega_silk_way", "botanical_garden", "expo_nur_alem", "nurzhol_boulevard"]
Minutes = Annotated[float, Field(ge=0, allow_inf_nan=False)]
NoRouteReason = Literal[
    "no_candidates",
    "unreachable",
    "budget_exceeded",
    "ors_unconfigured",
    "ors_timeout",
    "ors_unavailable",
    "ors_invalid_response",
]


class RoutePlanRequest(Model):
    start_anchor_id: AnchorID
    duration_minutes: int = Field(ge=30, le=180, strict=True)
    query: str = Field(min_length=1, max_length=1000, strict=True)
    round_trip: bool = Field(default=True, strict=True)
    language: Language = "ru"

    @field_validator("query")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must contain non-whitespace text")
        return value


class RouteStop(PublicPOI):
    order: int = Field(ge=1, le=3)
    visiting_minutes: int = Field(gt=0)
    visit_duration_source: Literal["planned_category_estimate"] = "planned_category_estimate"
    selection_source: Literal["retrieval", "nearby_fallback"]
    explanation: str


class RoutingProvenance(Model):
    matrix: GeoProvenance | None = None
    directions: GeoProvenance | None = None


class PlanBase(Model):
    start_anchor_id: AnchorID
    start_anchor: Anchor
    requested_duration_minutes: int = Field(ge=30, le=180)
    round_trip: bool
    language: Language
    retrieval_mode: RetrievalMode
    recommendation: str
    warnings: list[str]
    routing_provenance: RoutingProvenance
    dataset: DatasetMetadata


class RoutePlanSuccess(PlanBase):
    status: Literal["success"] = "success"
    estimated_total_minutes: Minutes
    walking_minutes: Minutes
    visiting_minutes: Minutes
    total_distance_meters: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    stops: list[RouteStop] = Field(min_length=1, max_length=3)
    route_geojson: RouteGeoJSON

    @model_validator(mode="after")
    def consistent_budget(self) -> Self:
        if self.estimated_total_minutes > self.requested_duration_minutes:
            raise ValueError("A successful route must fit the requested budget")
        if abs(self.walking_minutes + self.visiting_minutes - self.estimated_total_minutes) > 1e-9:
            raise ValueError("Total time must include walking and planned visits")
        if self.visiting_minutes != sum(stop.visiting_minutes for stop in self.stops):
            raise ValueError("Visit time must equal the planned stop durations")
        if [stop.order for stop in self.stops] != list(range(1, len(self.stops) + 1)):
            raise ValueError("Stops must be ordered consecutively")
        summary = self.route_geojson.features[0].properties.summary
        if self.walking_minutes != summary.duration / 60:
            raise ValueError("Walking time must come from the Directions summary")
        if self.total_distance_meters != summary.distance:
            raise ValueError("Distance must come from the Directions summary")
        if self.routing_provenance.matrix is None or self.routing_provenance.directions is None:
            raise ValueError("A successful route requires both ORS provenance records")
        return self


class RoutePlanUnavailable(PlanBase):
    status: Literal["no_route"] = "no_route"
    reason: NoRouteReason
    estimated_total_minutes: None = None
    walking_minutes: None = None
    visiting_minutes: None = None
    total_distance_meters: None = None
    stops: list[RouteStop] = Field(default_factory=list, max_length=0)
    route_geojson: None = None


RoutePlanResponse = Annotated[
    RoutePlanSuccess | RoutePlanUnavailable, Field(discriminator="status")
]
