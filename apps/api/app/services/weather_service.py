"""Typed service for HTTP and future Route Planner calls, with bounded TTL caching."""

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import get_args

from pydantic import ValidationError
from viberoute_geo import AnchorCatalog

from app.core.config import ROOT, Settings
from app.integrations.open_meteo import OpenMeteoClient, WeatherProviderError, local_timestamp
from app.schemas.weather import WEATHER_TZ, WeatherAnchorID, WeatherResponse

CacheKey = tuple[str, float, float, tuple[tuple[str, str], ...]]


def weather_now() -> datetime:
    return datetime.now(WEATHER_TZ)


@dataclass(frozen=True)
class CacheEntry:
    expires_at: float
    response: WeatherResponse


def assess_weather(weather: WeatherResponse, settings: Settings) -> list[str]:
    """Product heuristics only; absence of warnings is not a safety verdict."""
    warnings: list[str] = []
    if weather.wind_speed_kmh is not None and weather.wind_speed_kmh >= settings.weather_wind_kmh:
        warnings.append("weather_strong_wind")
    if (
        weather.precipitation_mm is not None
        and weather.precipitation_mm >= settings.weather_precipitation_mm
    ):
        warnings.append("weather_significant_precipitation")
    temperature = weather.apparent_temperature_c
    if temperature is None:
        temperature = weather.temperature_c
    if temperature is not None and temperature <= settings.weather_cold_c:
        warnings.append("weather_low_temperature")
    if (
        weather.precipitation_probability_percent is not None
        and weather.precipitation_probability_percent >= settings.weather_precipitation_probability
    ):
        warnings.append("weather_high_precipitation_probability")
    return warnings


class WeatherService:
    def __init__(
        self,
        client: OpenMeteoClient,
        settings: Settings,
        *,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = weather_now,
    ) -> None:
        self.client = client
        self.settings = settings
        self.clock = clock
        self.now = now
        catalog = AnchorCatalog.model_validate_json((ROOT / "shared/anchors.json").read_bytes())
        self.anchors = {
            anchor.id: anchor
            for anchor in catalog.anchors
            if anchor.id in get_args(WeatherAnchorID)
        }
        if set(self.anchors) != set(get_args(WeatherAnchorID)):
            raise ValueError("Weather requires all four catalog anchors")
        self._cache: OrderedDict[CacheKey, CacheEntry] = OrderedDict()
        # Sync FastAPI handlers run in worker threads. Coalesce concurrent cache misses.
        self._lock = Lock()

    def get_weather(self, anchor_id: WeatherAnchorID) -> WeatherResponse:
        if anchor_id not in self.anchors:
            raise ValueError("Unknown weather anchor")
        anchor = self.anchors[anchor_id]
        key = (
            anchor_id,
            anchor.location.latitude,
            anchor.location.longitude,
            self.client.parameters,
        )
        with self._lock:
            now = self.now().astimezone(WEATHER_TZ)
            cached = self._cache.get(key)
            if cached is not None and self.clock() < cached.expires_at:
                weather = cached.response
                current_fresh = weather.observed_at is None or (
                    timedelta(0) <= now - weather.observed_at <= timedelta(hours=2)
                )
                forecast_fresh = (
                    weather.forecast_valid_at is None or now < weather.forecast_valid_at
                )
                if current_fresh and forecast_fresh and now >= weather.fetched_at:
                    self._cache.move_to_end(key)
                    return weather.model_copy(update={"cache_status": "hit"}, deep=True)
            self._cache.pop(key, None)
            result = self._fetch(anchor_id, now)
            ttl = (
                self.settings.weather_cache_ttl_seconds
                if result.status == "available"
                else self.settings.weather_failure_ttl_seconds
            )
            self._cache[key] = CacheEntry(self.clock() + ttl, result.model_copy(deep=True))
            while len(self._cache) > self.settings.weather_cache_max_entries:
                self._cache.popitem(last=False)
            return result

    def _fetch(self, anchor_id: WeatherAnchorID, now: datetime) -> WeatherResponse:
        try:
            forecast = self.client.fetch(self.anchors[anchor_id], now)
        except WeatherProviderError as error:
            return WeatherResponse(
                status="unknown",
                anchor_id=anchor_id,
                fetched_at=self.now().astimezone(WEATHER_TZ),
                warnings=[error.code, "weather_conditions_unknown"],
            )
        now = self.now().astimezone(WEATHER_TZ)
        current = forecast.current
        warnings = ["weather_model_estimate_not_station_observation"]
        if current is None or any(
            getattr(current, field) is None
            for field in (
                "temperature_2m",
                "apparent_temperature",
                "precipitation",
                "wind_speed_10m",
                "weather_code",
            )
        ):
            warnings.append("weather_current_incomplete")
        probability = None
        valid_at = None
        hourly = forecast.hourly
        if hourly is not None and hourly.precipitation_probability is not None:
            for stamp, value in zip(hourly.time, hourly.precipitation_probability, strict=True):
                timestamp = local_timestamp(stamp)
                # Probability refers to (timestamp - 1h, timestamp], never to current conditions.
                if timedelta(0) < timestamp - now <= timedelta(hours=1):
                    probability = value
                    if value is not None:
                        valid_at = timestamp
                    break
        if probability is None:
            warnings.append("weather_hourly_probability_unavailable")
        current_values = (
            [
                getattr(current, field)
                for field in (
                    "temperature_2m",
                    "apparent_temperature",
                    "precipitation",
                    "wind_speed_10m",
                    "weather_code",
                )
            ]
            if current is not None
            else []
        )
        has_current = any(value is not None for value in current_values)
        if not has_current and probability is None:
            return WeatherResponse(
                status="unknown",
                anchor_id=anchor_id,
                fetched_at=now,
                warnings=[*warnings, "weather_conditions_unknown"],
            )
        try:
            result = WeatherResponse(
                status="available",
                anchor_id=anchor_id,
                temperature_c=current.temperature_2m if current else None,
                apparent_temperature_c=current.apparent_temperature if current else None,
                precipitation_mm=current.precipitation if current else None,
                precipitation_probability_percent=probability,
                wind_speed_kmh=current.wind_speed_10m if current else None,
                weather_code=current.weather_code if current else None,
                observed_at=local_timestamp(current.time) if current and has_current else None,
                forecast_valid_at=valid_at,
                fetched_at=now,
                warnings=warnings,
            )
        except ValidationError:
            # A slow request can cross the current-data freshness boundary after HTTP validation.
            return WeatherResponse(
                status="unknown",
                anchor_id=anchor_id,
                fetched_at=now,
                warnings=["weather_invalid_response", "weather_conditions_unknown"],
            )
        return result.model_copy(
            update={"warnings": [*warnings, *assess_weather(result, self.settings)]}
        )
