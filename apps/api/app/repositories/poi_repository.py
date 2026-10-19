"""Read and validate one immutable source snapshot during application startup."""

import hashlib
from pathlib import Path

from pydantic import ValidationError
from viberoute_data.models import POI, Dataset

from app.core.errors import DatasetLoadError
from app.schemas.poi import Attribution, DatasetMetadata, PublicPOI


class POIRepository:
    def __init__(self, dataset: Dataset, dataset_sha256: str) -> None:
        source = Attribution.from_dataset(dataset)
        self.metadata = DatasetMetadata(
            **source.model_dump(),
            dataset_sha256=dataset_sha256,
            raw_sha256=dataset.raw_sha256,
            collected_at=dataset.collected_at,
            osm_base_timestamp=dataset.osm_base_timestamp,
            endpoint=dataset.endpoint,
            schema_version=dataset.schema_version,
        )
        self.records: tuple[POI, ...] = tuple(sorted(dataset.pois, key=lambda poi: poi.id))
        self.items = tuple(PublicPOI.from_poi(poi, source) for poi in self.records)
        self.by_id = {poi.id: poi for poi in self.items}

    @classmethod
    def load(cls, path: Path) -> "POIRepository":
        try:
            raw = path.read_bytes()
            dataset = Dataset.model_validate_json(raw)
        except (OSError, ValidationError) as error:
            raise DatasetLoadError(
                "POI dataset is unavailable or invalid; startup aborted"
            ) from error
        return cls(dataset, hashlib.sha256(raw).hexdigest())
