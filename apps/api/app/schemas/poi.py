"""Public, source-backed POI contract. OSM evidence is not an independent survey."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl
from viberoute_data.models import POI, Dataset, Provenance

Category = Literal[
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


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Attribution(Model):
    attribution: str
    license: str
    license_url: HttpUrl

    @classmethod
    def from_dataset(cls, dataset: Dataset) -> "Attribution":
        return cls.model_validate({key: getattr(dataset, key) for key in cls.model_fields})


class DatasetMetadata(Attribution):
    dataset_sha256: str
    raw_sha256: str
    collected_at: AwareDatetime
    osm_base_timestamp: AwareDatetime | None
    endpoint: HttpUrl
    schema_version: str


class PublicPOI(Model):
    id: str = Field(pattern=r"^osm:(node|way|relation):[1-9][0-9]*$")
    name: str | None
    category: Category
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    coordinate_kind: Literal["osm_node", "bounding_box_center"]
    address: dict[str, str] | None
    opening_hours: str | None
    indoor: bool | None
    covered: bool | None
    wheelchair: Literal["yes", "no", "limited"] | None
    source_url: HttpUrl
    retrieved_at: AwareDatetime
    quality_warnings: list[str]
    provenance: Provenance
    source: Attribution
    verification_status: Literal["osm_source_only"] = "osm_source_only"

    @classmethod
    def from_poi(cls, poi: POI, source: Attribution) -> "PublicPOI":
        return cls(
            id=poi.id,
            name=poi.name,
            category=poi.category,
            latitude=poi.coordinates.latitude,
            longitude=poi.coordinates.longitude,
            coordinate_kind=poi.coordinates.kind,
            address=poi.address or None,
            opening_hours=poi.opening_hours,
            indoor=poi.attributes.indoor,
            covered=poi.attributes.covered,
            wheelchair=poi.attributes.wheelchair,
            source_url=poi.provenance.url,
            retrieved_at=poi.provenance.retrieved_at,
            quality_warnings=list(poi.quality_warnings),
            provenance=poi.provenance.model_copy(deep=True),
            source=source,
        )


class POIPage(Model):
    items: list[PublicPOI]
    total: int
    limit: int
    offset: int
    dataset: DatasetMetadata
