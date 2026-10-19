"""Validated, versioned dataset models; missing evidence stays unknown."""

import math
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class BoundingBox(Model):
    south: float = Field(ge=-90, le=90)
    west: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.south >= self.north or self.west >= self.east:
            raise ValueError("Expected south < north and west < east (no antimeridian crossing)")
        return self

    def ql(self) -> str:
        return f"{self.south},{self.west},{self.north},{self.east}"

    def contains(self, latitude: float, longitude: float) -> bool:
        return self.south <= latitude <= self.north and self.west <= longitude <= self.east


class Coordinates(Model):
    latitude: float = Field(ge=-90, le=90, strict=True)
    longitude: float = Field(ge=-180, le=180, strict=True)
    kind: Literal["osm_node", "bounding_box_center"]


class Attributes(Model):
    indoor: bool | None = None
    covered: bool | None = None
    wheelchair: Literal["yes", "no", "limited"] | None = None


class Provenance(Model):
    source: Literal["openstreetmap"] = "openstreetmap"
    url: HttpUrl
    element_type: Literal["node", "way", "relation"]
    element_id: int = Field(gt=0, strict=True)
    osm_version: int | None = Field(default=None, gt=0, strict=True)
    osm_updated_at: AwareDatetime | None = None
    retrieved_at: AwareDatetime
    field_tags: dict[str, list[str]]


class POI(Model):
    id: str = Field(pattern=r"^osm:(node|way|relation):[1-9][0-9]*$")
    name: str | None = Field(default=None, min_length=1)
    category: Literal[
        "cafe",
        "restaurant",
        "fast_food",
        "food_court",
        "library",
        "cinema",
        "theatre",
        "arts_centre",
        "community_centre",
        "museum",
        "gallery",
        "attraction",
        "artwork",
        "viewpoint",
        "park",
        "garden",
        "playground",
        "mall",
        "books",
    ]
    coordinates: Coordinates
    address: dict[str, str]
    opening_hours: str | None = Field(default=None, min_length=1)
    attributes: Attributes
    tags: dict[str, str]
    provenance: Provenance
    quality_warnings: list[str]

    @model_validator(mode="after")
    def consistent_identity(self) -> Self:
        source = self.provenance
        expected = f"osm:{source.element_type}:{source.element_id}"
        expected_url = f"https://www.openstreetmap.org/{source.element_type}/{source.element_id}"
        if self.id != expected or str(source.url) != expected_url:
            raise ValueError("POI identity and source URL must match the OSM element")
        return self


def finite_json(value: object) -> object:
    """Reject NaN/Infinity even in otherwise untyped Overpass payloads."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite JSON number")
    if isinstance(value, dict):
        for item in value.values():
            finite_json(item)
    elif isinstance(value, list):
        for item in value:
            finite_json(item)
    return value


class Capture(Model):
    format_version: Literal["1"] = "1"
    endpoint: HttpUrl
    bbox: BoundingBox
    query: str = Field(min_length=1)
    retrieved_at: AwareDatetime
    response: Annotated[dict[str, object], AfterValidator(finite_json)]


class CollectionStats(Model):
    input_elements: int = Field(ge=0)
    duplicate_elements: int = Field(ge=0)
    skipped_elements: int = Field(ge=0)
    output_pois: int = Field(ge=0)


class Dataset(Model):
    schema_version: Literal["0.1.0"] = "0.1.0"
    dataset_type: Literal["osm_snapshot"] = "osm_snapshot"
    attribution: Literal["© OpenStreetMap contributors"] = "© OpenStreetMap contributors"
    license: Literal["ODbL-1.0"] = "ODbL-1.0"
    license_url: Literal["https://www.openstreetmap.org/copyright"] = (
        "https://www.openstreetmap.org/copyright"
    )
    collected_at: AwareDatetime
    osm_base_timestamp: AwareDatetime | None = None
    endpoint: HttpUrl
    bbox: BoundingBox
    query: str
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stats: CollectionStats
    pois: list[POI]

    @model_validator(mode="after")
    def coherent_collection(self) -> Self:
        ids = [poi.id for poi in self.pois]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate POI IDs")
        stats = self.stats
        if stats.output_pois != len(ids):
            raise ValueError("Output count does not match POIs")
        if stats.input_elements != (
            stats.output_pois + stats.skipped_elements + stats.duplicate_elements
        ):
            raise ValueError("Collection counts do not add up")
        for poi in self.pois:
            point = poi.coordinates
            if not self.bbox.contains(point.latitude, point.longitude):
                raise ValueError(f"POI outside collection bbox: {poi.id}")
            if poi.provenance.retrieved_at != self.collected_at:
                raise ValueError("Retrieval timestamps must match the capture")
        return self
