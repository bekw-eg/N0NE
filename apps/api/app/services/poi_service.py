import unicodedata

from app.repositories.poi_repository import POIRepository
from app.schemas.poi import Category, POIPage, PublicPOI


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


class POIService:
    def __init__(self, repository: POIRepository) -> None:
        self.repository = repository
        self.texts = {
            poi.id: normalize(
                " ".join(
                    [
                        poi.name or "",
                        poi.category,
                        *poi.address.values(),
                        *(
                            value
                            for key, value in poi.tags.items()
                            if key == "name" or key.startswith("name:")
                        ),
                    ]
                )
            )
            for poi in repository.records
        }

    def search(self, q: str, category: Category | None, limit: int, offset: int) -> POIPage:
        query = normalize(q)
        found = [
            poi
            for poi in self.repository.items
            if (category is None or poi.category == category) and query in self.texts[poi.id]
        ]
        return POIPage(
            items=found[offset : offset + limit],
            total=len(found),
            limit=limit,
            offset=offset,
            dataset=self.repository.metadata,
        )

    def get(self, poi_id: str) -> PublicPOI | None:
        return self.repository.by_id.get(poi_id)
