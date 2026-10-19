"""Source fields only; taxonomy translations do not add geographic attributes."""

import re

from viberoute_data.models import POI

from app.services.poi_service import normalize

TEXT_VERSION = "source-fields-v1"
CATEGORY_WORDS = {
    "cafe": "кафе кофейня кофейни дәмхана",
    "restaurant": "ресторан рестораны мейрамхана",
    "fast_food": "фастфуд жылдам тағам",
    "food_court": "фудкорт",
    "library": "библиотека библиотеки кітапхана",
    "cinema": "кинотеатр кино кинотеатрлар",
    "theatre": "театр театрлар",
    "arts_centre": "центр искусств өнер орталығы",
    "community_centre": "общественный центр қоғамдық орталық",
    "museum": "музей музеи мұражай",
    "gallery": "галерея",
    "attraction": "достопримечательность көрікті орын",
    "artwork": "произведение искусства өнер туындысы",
    "viewpoint": "смотровая площадка көрініс алаңы",
    "park": "парк парки саябақ саябақтар",
    "garden": "сад сады бақ бақтар",
    "playground": "детская площадка ойын алаңы",
    "mall": "торговый центр сауда орталығы",
    "books": "книжный магазин кітап дүкені",
}
SAFE_TAGS = {"brand", "cuisine", "internet_access", "outdoor_seating"}


def tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", normalize(text))


def document(poi: POI) -> str:
    fields = [poi.name or "", poi.category, CATEGORY_WORDS[poi.category], *poi.address.values()]
    fields.extend(
        f"{key}: {value}"
        for key, value in sorted(poi.tags.items())
        if key in SAFE_TAGS or key.startswith("name:")
    )
    for key in ("indoor", "covered", "wheelchair"):
        value = getattr(poi.attributes, key)
        if value is not None:
            fields.append(f"{key}: {value}")
    return "\n".join(fields)
