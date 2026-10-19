"""Small, synchronous Open-Meteo HTTP adapter with strict upstream validation."""

import re
from datetime import datetime, timedelta
from typing import Literal, Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from viberoute_geo import Anchor

from app.schemas.weather import (
    WEATHER_TIMEZONE,
    WEATHER_TZ,
    Precipitation,
    Probability,
    Temperature,
    WeatherCode,
    WindSpeed,
)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_UNITS = {
    "temperature_2m": "°C",
    "apparent_temperature": "°C",
    "precipitation": "mm",
    "wind_speed_10m": "km/h",
    "weather_code": "wmo code",
}


class WeatherProviderError(RuntimeError):
    """Only a safe machine-readable code crosses the adapter boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class UpstreamModel(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, allow_inf_nan=False)


class CurrentWeather(UpstreamModel):
    time: str
    temperature_2m: Temperature | None = None
    apparent_temperature: Temperature | None = None
    precipitation: Precipitation | None = None
    wind_speed_10m: WindSpeed | None = None
    weather_code: WeatherCode | None = None


class HourlyWeather(UpstreamModel):
    time: list[str] = Field(max_length=6)
    precipitation_probability: list[Probability | None] | None = Field(default=None, max_length=6)

    @model_validator(mode="after")
    def aligned_arrays(self) -> Self:
        if self.precipitation_probability is not None and len(self.time) != len(
            self.precipitation_probability
        ):
            raise ValueError("Hourly array lengths differ")
        return self


class OpenMeteoForecast(UpstreamModel):
    timezone: Literal["Asia/Almaty"]
    utc_offset_seconds: int
    current: CurrentWeather | None = None
    hourly: HourlyWeather | None = None
    current_units: dict[str, str] = Field(default_factory=dict)
    hourly_units: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def correct_units(self) -> Self:
        if self.current is not None:
            for field, unit in CURRENT_UNITS.items():
                if (
                    getattr(self.current, field) is not None
                    and self.current_units.get(field) != unit
                ):
                    raise ValueError("Unexpected current weather unit")
        if (
            self.hourly is not None
            and self.hourly.precipitation_probability is not None
            and any(value is not None for value in self.hourly.precipitation_probability)
            and self.hourly_units.get("precipitation_probability") != "%"
        ):
            raise ValueError("Unexpected precipitation probability unit")
        return self


def local_timestamp(value: str) -> datetime:
    """Open-Meteo ISO timestamps are local; reject dates, epochs and foreign offsets."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?", value):
        raise ValueError("Invalid weather timestamp")
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=WEATHER_TZ)
    if stamp.utcoffset() != stamp.astimezone(WEATHER_TZ).utcoffset():
        raise ValueError("Invalid weather timestamp offset")
    return stamp.astimezone(WEATHER_TZ)


class OpenMeteoClient:
    def __init__(
        self, client: httpx.Client, *, timeout_seconds: float = 5, forecast_hours: int = 3
    ) -> None:
        if not 0 < timeout_seconds <= 30 or not 2 <= forecast_hours <= 6:
            raise ValueError("Invalid Open-Meteo request configuration")
        self.client = client
        self.timeout = httpx.Timeout(timeout_seconds, connect=min(3, timeout_seconds))
        self.parameters = (
            ("current", ",".join(CURRENT_UNITS)),
            ("hourly", "precipitation_probability"),
            ("timezone", WEATHER_TIMEZONE),
            ("temperature_unit", "celsius"),
            ("wind_speed_unit", "kmh"),
            ("precipitation_unit", "mm"),
            ("timeformat", "iso8601"),
            ("forecast_hours", str(forecast_hours)),
        )

    def fetch(self, anchor: Anchor, now: datetime) -> OpenMeteoForecast:
        params = dict(self.parameters)
        params.update(
            latitude=str(anchor.location.latitude), longitude=str(anchor.location.longitude)
        )
        try:
            response = self.client.get(OPEN_METEO_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise WeatherProviderError("weather_timeout") from error
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            code = "weather_rate_limited" if status == 429 else "weather_http_error"
            if status >= 500:
                code = "weather_upstream_unavailable"
            raise WeatherProviderError(code) from error
        except httpx.RequestError as error:
            raise WeatherProviderError("weather_connection_error") from error
        try:
            raw = response.json()
        except (ValueError, UnicodeError) as error:
            raise WeatherProviderError("weather_invalid_json") from error
        try:
            result = OpenMeteoForecast.model_validate(raw)
            offset = now.utcoffset()
            if offset is None or result.utc_offset_seconds != int(offset.total_seconds()):
                raise ValueError("Invalid timezone offset metadata")
            if result.current is not None:
                observed = local_timestamp(result.current.time)
                if not timedelta(0) <= now - observed <= timedelta(hours=2):
                    raise ValueError("Stale or future current weather")
            if result.hourly is not None:
                times = [local_timestamp(stamp) for stamp in result.hourly.time]
                if any(
                    later - earlier != timedelta(hours=1)
                    for earlier, later in zip(times, times[1:], strict=False)
                ):
                    raise ValueError("Hourly timestamps must increase in one-hour steps")
                if any(stamp.minute or stamp.second for stamp in times):
                    raise ValueError("Hourly timestamps must lie on hour boundaries")
        except (ValidationError, ValueError, OverflowError) as error:
            raise WeatherProviderError("weather_invalid_response") from error
        return result
