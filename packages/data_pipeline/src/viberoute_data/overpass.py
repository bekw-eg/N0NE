"""Bounded Overpass requests with explicit errors and bounded retry backoff."""

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

import httpx
from pydantic import HttpUrl

from .models import BoundingBox, Capture

LOGGER = logging.getLogger(__name__)
DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"
CATEGORY_VALUES: dict[str, tuple[str, ...]] = {
    "amenity": (
        "cafe",
        "restaurant",
        "fast_food",
        "food_court",
        "library",
        "cinema",
        "theatre",
        "arts_centre",
        "community_centre",
    ),
    "tourism": ("museum", "gallery", "attraction", "artwork", "viewpoint"),
    "leisure": ("park", "garden", "playground"),
    "shop": ("mall", "books"),
}


class CollectionError(RuntimeError):
    """The upstream request cannot be treated as a complete POI snapshot."""


def build_query(bbox: BoundingBox) -> str:
    selections = "\n".join(
        f'  nwr["{key}"~"^({"|".join(values)})$"]({bbox.ql()});'
        for key, values in CATEGORY_VALUES.items()
    )
    return f"[out:json][timeout:60];\n(\n{selections}\n);\nout meta center;\n"


def check_response(response: object) -> dict[str, object]:
    if not isinstance(response, dict) or not isinstance(response.get("elements"), list):
        raise CollectionError("Overpass response must contain an elements array")
    if response.get("remark"):
        raise CollectionError("Overpass reported a runtime error; partial data rejected")
    if not all(isinstance(item, dict) for item in response["elements"]):
        raise CollectionError("Overpass elements must be objects")
    return cast(dict[str, object], response)


def collect(
    bbox: BoundingBox,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Capture:
    if client is None:
        with httpx.Client(timeout=httpx.Timeout(80, connect=15)) as owned_client:
            return collect(bbox, endpoint=endpoint, client=owned_client, sleep=sleep)
    query = build_query(bbox)
    for attempt in range(3):
        try:
            result = client.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": "VibeRoute/0.1 (+https://github.com/bekw-eg/N0NE)"},
            )
        except httpx.TransportError as exc:
            if attempt == 2:
                raise CollectionError("Overpass transport failed after 3 attempts") from exc
            sleep(float(2 ** (attempt + 1)))
            continue
        if result.status_code in {429, 502, 503, 504} and attempt < 2:
            retry_after = result.headers.get("Retry-After", "")
            delay = min(float(retry_after), 30.0) if retry_after.isdecimal() else 2 ** (attempt + 1)
            LOGGER.warning(
                "overpass_retry", extra={"status": result.status_code, "attempt": attempt}
            )
            sleep(delay)
            continue
        try:
            result.raise_for_status()
            payload = check_response(result.json())
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise CollectionError("Overpass returned an HTTP error or invalid JSON") from exc
        # Author/user IDs are unnecessary for POI provenance; retain object version and timestamp.
        for element in cast(list[dict[str, object]], payload["elements"]):
            element.pop("user", None)
            element.pop("uid", None)
        return Capture(
            endpoint=HttpUrl(endpoint),
            bbox=bbox,
            query=query,
            retrieved_at=datetime.now(UTC),
            response=payload,
        )
    raise CollectionError("Overpass request failed")
