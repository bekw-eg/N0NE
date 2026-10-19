"""Source-backed public anchors; mapped entrances are not field surveys."""

import re
from typing import Literal, Self

from pydantic import AwareDatetime, Field, HttpUrl, model_validator

from .models import GeoPoint, Model


class SourcePoint(Model):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    location: GeoPoint
    coordinate_kind: Literal["osm_node", "bounding_box_center", "mapped_entrance"]
    source_url: HttpUrl
    osm_version: int = Field(gt=0, strict=True)
    osm_updated_at: AwareDatetime
    retrieved_at: AwareDatetime
    osm_tags: dict[str, str] = Field(default_factory=dict)
    verification_status: Literal["unknown", "source_verified"] = "unknown"
    entrance_status: Literal["unknown", "osm_mapped"] = "unknown"
    landmark_source_url: HttpUrl | None = None
    # Neither source verification nor a successful route establishes these facts.
    accessibility_status: Literal["unknown"] = "unknown"
    opening_status: Literal["unknown"] = "unknown"
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_matches_claim(self) -> Self:
        if self.osm_updated_at > self.retrieved_at:
            raise ValueError("OSM update cannot be later than retrieval")
        if self.verification_status == "source_verified":
            object_kind = (
                "(?:way|relation)" if self.coordinate_kind == "bounding_box_center" else "node"
            )
            if (
                self.source_url.scheme != "https"
                or self.source_url.host != "www.openstreetmap.org"
                or self.source_url.username
                or self.source_url.password
                or self.source_url.query
                or self.source_url.fragment
                or not re.fullmatch(rf"/{object_kind}/[1-9][0-9]*", self.source_url.path or "")
            ):
                raise ValueError("Verified OSM coordinate requires a matching public object URL")
        if self.entrance_status == "osm_mapped" or self.coordinate_kind == "mapped_entrance":
            if (
                self.coordinate_kind != "mapped_entrance"
                or self.entrance_status != "osm_mapped"
                or self.verification_status != "source_verified"
                or self.osm_tags.get("entrance") not in {"yes", "main", "entrance"}
                or self.source_url.host != "www.openstreetmap.org"
                or not (self.source_url.path or "").startswith("/node/")
                or self.landmark_source_url is None
                or not re.fullmatch(
                    r"https://www\.openstreetmap\.org/(?:way|relation)/[1-9][0-9]*",
                    str(self.landmark_source_url),
                )
            ):
                raise ValueError("Mapped entrance requires node evidence and landmark association")
        return self


class Anchor(SourcePoint):
    alternative_entrances: list[SourcePoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def entrances_have_evidence(self) -> Self:
        if any(point.coordinate_kind != "mapped_entrance" for point in self.alternative_entrances):
            raise ValueError("Alternative entrances require mapped entrance evidence")
        landmark = self.landmark_source_url or self.source_url
        if any(point.landmark_source_url != landmark for point in self.alternative_entrances):
            raise ValueError("Alternative entrances must refer to the same landmark")
        return self


class AnchorCatalog(Model):
    # Old 0.1.0 catalogs load with conservative unknown defaults.
    schema_version: Literal["0.1.0", "0.2.0"]
    description: str
    anchors: list[Anchor] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        ids = [
            point.id for anchor in self.anchors for point in [anchor, *anchor.alternative_entrances]
        ]
        if len(set(ids)) != len(ids):
            raise ValueError("Anchor and alternative entrance IDs must be unique")
        return self
