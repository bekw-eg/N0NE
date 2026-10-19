"""ORS graph routes only; offline responses require an exact recorded request."""

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

import httpx
from pydantic import HttpUrl, JsonValue, SecretStr, ValidationError

from .models import (
    DirectionsRequest,
    GeoCapture,
    GeoProvenance,
    IsochronesGeoJSON,
    IsochronesRequest,
    IsochronesResult,
    MatrixData,
    MatrixRequest,
    MatrixResult,
    Operation,
    RouteGeoJSON,
    RouteResult,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://api.openrouteservice.org"
SUFFIXES: dict[Operation, str] = {
    "directions": "/v2/directions/foot-walking/geojson",
    "isochrones": "/v2/isochrones/foot-walking",
    "matrix": "/v2/matrix/foot-walking",
}


class GeoError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int | None = None,
        provider_code: int | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.status = status
        self.provider_code = provider_code


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def recording_name(operation: Operation, payload: dict[str, JsonValue]) -> str:
    digest = hashlib.sha256(
        canonical({"operation": operation, "profile": "foot-walking", "request": payload})
    ).hexdigest()
    return f"{operation}-{digest}.json"


def redact(value: JsonValue, secret: str) -> JsonValue:
    if isinstance(value, dict):
        return {
            key: redact(item, secret)
            for key, item in value.items()
            if key.casefold() not in {"authorization", "api_key", "apikey", "access_token", "token"}
        }
    if isinstance(value, list):
        return [redact(item, secret) for item in value]
    if isinstance(value, str) and secret:
        return value.replace(secret, "[REDACTED]")
    return value


class GeoAdapter:
    """Internal adapter for public POIs/anchors and already privacy-reduced origins.

    This class exposes no HTTP GPS-intake endpoint. Recording is opt-in, and
    offline mode is explicit; live failures never manufacture a path.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        recordings_dir: Path | None = None,
        mode: Literal["live", "recorded"] = "live",
        max_recording_age_seconds: int = 86400,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        url = HttpUrl(base_url)
        if url.scheme != "https" or url.username or url.password or url.query or url.fragment:
            raise ValueError("ORS base URL must be HTTPS without credentials, query, or fragment")
        if max_recording_age_seconds <= 0:
            raise ValueError("Recording age limit must be positive")
        if mode not in {"live", "recorded"}:
            raise ValueError("Mode must be live or recorded")
        if mode == "recorded" and recordings_dir is None:
            raise ValueError("Recorded mode requires a recordings directory")
        self._base_url = str(url).rstrip("/")
        self._key = SecretStr(api_key or "")
        self._client = client
        self._recordings_dir = recordings_dir
        self._mode = mode
        self._max_age = max_recording_age_seconds
        self._sleep = sleep
        self._now = now

    @classmethod
    def from_env(cls) -> "GeoAdapter":
        return cls(
            api_key=os.environ.get("ORS_API_KEY"),
            base_url=os.environ.get("ORS_BASE_URL", DEFAULT_BASE_URL),
        )

    def _endpoint(self, operation: Operation) -> str:
        return self._base_url + SUFFIXES[operation]

    def _read_recording(self, operation: Operation, payload: dict[str, JsonValue]) -> GeoCapture:
        assert self._recordings_dir is not None
        path = self._recordings_dir / recording_name(operation, payload)
        try:
            capture = GeoCapture.model_validate_json(path.read_bytes())
        except (OSError, ValueError) as exc:
            raise GeoError(
                "recording_unavailable", "No valid recorded ORS response for this exact request"
            ) from exc
        if (
            capture.operation != operation
            or capture.request != payload
            or str(capture.endpoint) != self._endpoint(operation)
        ):
            raise GeoError("recording_mismatch", "Recorded ORS request or endpoint does not match")
        try:
            actual_hash = hashlib.sha256(canonical(capture.response)).hexdigest()
        except (ValueError, TypeError):
            raise GeoError(
                "recording_corrupt", "Recorded ORS response is not finite JSON"
            ) from None
        if actual_hash != capture.response_sha256:
            raise GeoError("recording_corrupt", "Recorded ORS response hash does not match")
        age = (self._now() - capture.retrieved_at).total_seconds()
        if age < -300 or age > self._max_age:
            raise GeoError(
                "recording_stale", "Recorded ORS response is outside the allowed age window"
            )
        return capture

    def _post(self, operation: Operation, payload: dict[str, JsonValue]) -> GeoCapture:
        if self._mode == "recorded":
            return self._read_recording(operation, payload)
        secret = self._key.get_secret_value()
        if not secret.strip():
            raise GeoError("configuration_missing", "Set ORS_API_KEY to call OpenRouteService")
        if self._client is None:
            with httpx.Client(
                timeout=httpx.Timeout(60, connect=10), follow_redirects=False
            ) as client:
                return self._post_with_client(client, operation, payload, secret)
        return self._post_with_client(self._client, operation, payload, secret)

    def _post_with_client(
        self,
        client: httpx.Client,
        operation: Operation,
        payload: dict[str, JsonValue],
        secret: str,
    ) -> GeoCapture:
        for attempt in range(3):
            try:
                response = client.post(
                    self._endpoint(operation),
                    json=payload,
                    headers={
                        "Authorization": secret,
                        "Accept": "application/json, application/geo+json",
                    },
                    follow_redirects=False,
                )
            except httpx.TransportError:
                if attempt == 2:
                    raise GeoError(
                        "transport_error", "ORS transport failed after three attempts"
                    ) from None
                self._sleep(float(2 ** (attempt + 1)))
                continue
            if response.status_code in {429, 502, 503, 504} and attempt < 2:
                retry_after = response.headers.get("Retry-After", "")
                delay = (
                    min(float(retry_after), 30.0)
                    if retry_after.isdecimal()
                    else float(2 ** (attempt + 1))
                )
                LOGGER.warning(
                    "ors_retry", extra={"operation": operation, "status": response.status_code}
                )
                self._sleep(delay)
                continue
            if response.status_code != 200:
                code = (
                    "authentication_error"
                    if response.status_code in {401, 403}
                    else "provider_error"
                )
                if response.status_code == 429:
                    code = "rate_limited"
                provider_code = None
                try:
                    error = response.json().get("error", {})
                    candidate = error.get("code") if isinstance(error, dict) else None
                    if type(candidate) is int:
                        provider_code = candidate
                except (ValueError, AttributeError):
                    pass
                raise GeoError(
                    code,
                    "ORS rejected the walking request",
                    status=response.status_code,
                    provider_code=provider_code,
                )
            try:
                document = response.json()
                if not isinstance(document, dict) or "error" in document:
                    raise ValueError("Expected a successful ORS object")
                sanitized = cast(dict[str, JsonValue], redact(document, secret))
                digest = hashlib.sha256(canonical(sanitized)).hexdigest()
                return GeoCapture(
                    operation=operation,
                    endpoint=HttpUrl(self._endpoint(operation)),
                    retrieved_at=self._now(),
                    request=payload,
                    response=sanitized,
                    response_sha256=digest,
                )
            except (ValueError, TypeError):
                raise GeoError(
                    "invalid_response", "ORS returned invalid JSON or non-finite data"
                ) from None
        raise GeoError("transport_error", "ORS request exhausted its retry limit")

    def _provenance(self, capture: GeoCapture) -> GeoProvenance:
        metadata = capture.response.get("metadata", {})
        return GeoProvenance(
            mode=self._mode,
            retrieved_at=capture.retrieved_at,
            endpoint=capture.endpoint,
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    def _save(self, capture: GeoCapture) -> None:
        if self._mode == "recorded" or self._recordings_dir is None:
            return
        path = self._recordings_dir / recording_name(capture.operation, capture.request)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(capture.model_dump_json(indent=2).encode("utf-8") + b"\n")
            temporary.replace(path)
        except OSError:
            raise GeoError(
                "recording_failed", "Could not save the validated ORS response"
            ) from None
        finally:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)

    def directions(self, request: DirectionsRequest) -> RouteResult:
        capture = self._post("directions", request.payload())
        try:
            geojson = RouteGeoJSON.model_validate(capture.response)
            if len(geojson.features[0].properties.way_points) != len(request.locations):
                raise ValueError("Waypoint count does not match request")
        except (ValidationError, ValueError):
            raise GeoError("invalid_response", "ORS route geometry or summary is invalid") from None
        self._save(capture)
        return RouteResult(geojson=geojson, provenance=self._provenance(capture))

    def isochrones(self, request: IsochronesRequest) -> IsochronesResult:
        capture = self._post("isochrones", request.payload())
        try:
            geojson = IsochronesGeoJSON.model_validate(capture.response)
            values = sorted(feature.properties.value for feature in geojson.features)
            if values != list(request.ranges_seconds):
                raise ValueError("Returned isochrone ranges do not match request")
        except (ValidationError, ValueError):
            raise GeoError(
                "invalid_response", "ORS isochrone geometry or ranges are invalid"
            ) from None
        self._save(capture)
        return IsochronesResult(geojson=geojson, provenance=self._provenance(capture))

    def matrix(self, request: MatrixRequest) -> MatrixResult:
        capture = self._post("matrix", request.payload())
        try:
            data = MatrixData.model_validate(capture.response)
            rows, columns = len(request.source_indices), len(request.destination_indices)
            if len(data.sources) != rows or len(data.destinations) != columns:
                raise ValueError("Snapped location counts do not match request")
            if len(data.durations) != rows or len(data.distances) != rows:
                raise ValueError("Matrix row counts do not match request")
            for row, (durations, distances) in enumerate(
                zip(data.durations, data.distances, strict=True)
            ):
                if len(durations) != columns or len(distances) != columns:
                    raise ValueError("Matrix column counts do not match request")
                if any(
                    (duration is None) != (distance is None)
                    for duration, distance in zip(durations, distances, strict=True)
                ):
                    raise ValueError("Matrix reachability metrics disagree")
                for column, duration in enumerate(durations):
                    if (
                        data.sources[row] is None or data.destinations[column] is None
                    ) and duration is not None:
                        raise ValueError("Unsnapped locations cannot have finite travel times")
        except (ValidationError, ValueError):
            raise GeoError(
                "invalid_response", "ORS matrix dimensions or metrics are invalid"
            ) from None
        self._save(capture)
        return MatrixResult(
            data=data,
            source_indices=request.source_indices,
            destination_indices=request.destination_indices,
            provenance=self._provenance(capture),
        )
