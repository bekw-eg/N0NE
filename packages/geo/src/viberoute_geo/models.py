"""Internal geo contracts; no shared recommendation/API schema is defined here."""

from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    JsonValue,
    model_validator,
)

Longitude = Annotated[float, Field(ge=-180, le=180, strict=True, allow_inf_nan=False)]
Latitude = Annotated[float, Field(ge=-90, le=90, strict=True, allow_inf_nan=False)]
Position = tuple[Longitude, Latitude]
Nonnegative = Annotated[float, Field(ge=0, strict=True, allow_inf_nan=False)]
Index = Annotated[int, Field(ge=0, strict=True)]
RangeSeconds = Annotated[int, Field(gt=0, le=900, strict=True)]
Operation = Literal["directions", "isochrones", "matrix"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ProviderModel(BaseModel):
    # ORS can add fields without invalidating known, strictly checked geometry/metrics.
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)


class GeoPoint(Model):
    longitude: Longitude
    latitude: Latitude

    def ors(self) -> list[JsonValue]:
        return [self.longitude, self.latitude]


class DirectionsRequest(Model):
    locations: Annotated[list[GeoPoint], Field(min_length=2, max_length=25)]
    snap_radius_m: Annotated[float, Field(ge=1, le=1000, allow_inf_nan=False)] = 100.0

    def payload(self) -> dict[str, JsonValue]:
        return {
            "coordinates": [point.ors() for point in self.locations],
            "radiuses": [self.snap_radius_m] * len(self.locations),
            "instructions": False,
            "elevation": False,
            "units": "m",
        }


class IsochronesRequest(Model):
    origin: GeoPoint
    ranges_seconds: Annotated[tuple[RangeSeconds, ...], Field(min_length=1, max_length=2)] = (
        600,
        900,
    )

    @model_validator(mode="after")
    def ordered_ranges(self) -> Self:
        if tuple(sorted(set(self.ranges_seconds))) != self.ranges_seconds:
            raise ValueError("Isochrone ranges must be unique and increasing")
        return self

    def payload(self) -> dict[str, JsonValue]:
        return {
            "locations": [self.origin.ors()],
            "range": list(self.ranges_seconds),
            "range_type": "time",
        }


class MatrixRequest(Model):
    locations: Annotated[list[GeoPoint], Field(min_length=1, max_length=50)]
    sources: list[Index] | None = None
    destinations: list[Index] | None = None

    @model_validator(mode="after")
    def valid_indices(self) -> Self:
        for indices in (self.sources, self.destinations):
            if indices is not None and (
                not indices
                or len(set(indices)) != len(indices)
                or any(index >= len(self.locations) for index in indices)
            ):
                raise ValueError("Matrix indices must be nonempty, unique, and within locations")
        return self

    @property
    def source_indices(self) -> list[int]:
        return self.sources if self.sources is not None else list(range(len(self.locations)))

    @property
    def destination_indices(self) -> list[int]:
        return (
            self.destinations if self.destinations is not None else list(range(len(self.locations)))
        )

    def payload(self) -> dict[str, JsonValue]:
        return {
            "locations": [point.ors() for point in self.locations],
            "sources": [str(index) for index in self.source_indices],
            "destinations": [str(index) for index in self.destination_indices],
            "metrics": ["duration", "distance"],
            "units": "m",
            "resolve_locations": True,
        }


class LineString(Model):
    type: Literal["LineString"]
    coordinates: Annotated[list[Position], Field(min_length=2)]


class RouteSummary(ProviderModel):
    distance: Nonnegative
    duration: Nonnegative


class RouteProperties(ProviderModel):
    summary: RouteSummary
    way_points: Annotated[list[Index], Field(min_length=2)]
    warnings: list[dict[str, JsonValue]] = Field(default_factory=list)


class RouteFeature(ProviderModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: RouteProperties

    @model_validator(mode="after")
    def valid_waypoints(self) -> Self:
        indices = self.properties.way_points
        if (
            indices != sorted(indices)
            or indices[0] != 0
            or indices[-1] != len(self.geometry.coordinates) - 1
        ):
            raise ValueError("Route waypoint indices must cover the geometry in order")
        return self


class RouteGeoJSON(ProviderModel):
    type: Literal["FeatureCollection"]
    features: Annotated[list[RouteFeature], Field(min_length=1, max_length=1)]


def closed_ring(ring: list[Position]) -> list[Position]:
    if ring[0] != ring[-1]:
        raise ValueError("Polygon ring must be closed")
    return ring


Ring = Annotated[list[Position], Field(min_length=4), AfterValidator(closed_ring)]


class Polygon(Model):
    type: Literal["Polygon"]
    coordinates: Annotated[list[Ring], Field(min_length=1)]


class MultiPolygon(Model):
    type: Literal["MultiPolygon"]
    coordinates: Annotated[list[Annotated[list[Ring], Field(min_length=1)]], Field(min_length=1)]


class IsochroneProperties(ProviderModel):
    group_index: Literal[0]
    value: Nonnegative
    center: Position


class IsochroneFeature(ProviderModel):
    type: Literal["Feature"]
    geometry: Annotated[Polygon | MultiPolygon, Field(discriminator="type")]
    properties: IsochroneProperties


class IsochronesGeoJSON(ProviderModel):
    type: Literal["FeatureCollection"]
    features: Annotated[list[IsochroneFeature], Field(min_length=1, max_length=2)]


class SnappedLocation(ProviderModel):
    location: Position
    snapped_distance: Nonnegative
    name: str | None = None


class MatrixData(ProviderModel):
    durations: list[list[Nonnegative | None]]
    distances: list[list[Nonnegative | None]]
    sources: list[SnappedLocation | None]
    destinations: list[SnappedLocation | None]


class GeoProvenance(Model):
    provider: Literal["openrouteservice"] = "openrouteservice"
    profile: Literal["foot-walking"] = "foot-walking"
    mode: Literal["live", "recorded"]
    retrieved_at: AwareDatetime
    endpoint: HttpUrl
    metadata: dict[str, JsonValue]


class RouteResult(Model):
    geojson: RouteGeoJSON
    provenance: GeoProvenance

    @property
    def duration_seconds(self) -> float:
        return self.geojson.features[0].properties.summary.duration

    @property
    def distance_meters(self) -> float:
        return self.geojson.features[0].properties.summary.distance


class IsochronesResult(Model):
    geojson: IsochronesGeoJSON
    provenance: GeoProvenance


class MatrixResult(Model):
    data: MatrixData
    source_indices: list[int]
    destination_indices: list[int]
    provenance: GeoProvenance


class GeoCapture(Model):
    format_version: Literal["1"] = "1"
    operation: Operation
    profile: Literal["foot-walking"] = "foot-walking"
    endpoint: HttpUrl
    retrieved_at: AwareDatetime
    request: dict[str, JsonValue]
    response: dict[str, JsonValue]
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
