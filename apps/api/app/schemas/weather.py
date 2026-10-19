"""Anchor-only weather contract; missing evidence is always nullable."""

from datetime import timedelta
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

WEATHER_TIMEZONE: Literal["Asia/Almaty"] = "Asia/Almaty"
WEATHER_TZ = ZoneInfo(WEATHER_TIMEZONE)
WeatherAnchorID = Literal["expo_nur_alem", "mega_silk_way", "botanical_garden", "nurzhol_boulevard"]
Temperature = Annotated[float, Field(strict=True, ge=-100, le=70, allow_inf_nan=False)]
Precipitation = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Probability = Annotated[float, Field(strict=True, ge=0, le=100, allow_inf_nan=False)]
WindSpeed = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


def strict_weather_code(value: object) -> object:
    if type(value) is not int:
        raise ValueError("WMO weather code must be an integer")
    return value


WeatherCode = Annotated[
    Literal[
        0,
        1,
        2,
        3,
        45,
        48,
        51,
        53,
        55,
        56,
        57,
        61,
        63,
        65,
        66,
        67,
        71,
        73,
        75,
        77,
        80,
        81,
        82,
        85,
        86,
        95,
        96,
        99,
    ],
    BeforeValidator(strict_weather_code),
]


class WeatherQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_anchor_id: WeatherAnchorID


class WeatherResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)

    status: Literal["available", "unknown"]
    anchor_id: WeatherAnchorID
    temperature_c: Temperature | None = None
    apparent_temperature_c: Temperature | None = None
    precipitation_mm: Precipitation | None = None
    precipitation_probability_percent: Probability | None = None
    wind_speed_kmh: WindSpeed | None = None
    weather_code: WeatherCode | None = None
    timezone: Literal["Asia/Almaty"] = WEATHER_TIMEZONE
    observed_at: AwareDatetime | None = Field(
        default=None, description="Timestamp of Open-Meteo current model conditions, not a station."
    )
    forecast_valid_at: AwareDatetime | None = Field(
        default=None, description="End of the preceding-hour precipitation probability interval."
    )
    fetched_at: AwareDatetime
    source: Literal["open-meteo"] = "open-meteo"
    cache_status: Literal["hit", "miss"] = "miss"
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_evidence(self) -> Self:
        current = (
            self.temperature_c,
            self.apparent_temperature_c,
            self.precipitation_mm,
            self.wind_speed_kmh,
            self.weather_code,
        )
        has_current = any(value is not None for value in current)
        has_probability = self.precipitation_probability_percent is not None
        if self.status == "unknown":
            if has_current or has_probability or self.observed_at or self.forecast_valid_at:
                raise ValueError("Unknown weather cannot contain weather evidence")
            if not self.warnings:
                raise ValueError("Unknown weather requires a warning")
        elif not has_current and not has_probability:
            raise ValueError("Available weather requires at least one weather indicator")
        if has_current != (self.observed_at is not None):
            raise ValueError("Current conditions require their own timestamp")
        if has_probability != (self.forecast_valid_at is not None):
            raise ValueError("Probability requires its own forecast timestamp")
        for stamp in (self.observed_at, self.forecast_valid_at, self.fetched_at):
            if stamp is not None and stamp.utcoffset() != stamp.astimezone(WEATHER_TZ).utcoffset():
                raise ValueError("Weather timestamps must use the Asia/Almaty UTC offset")
        if self.observed_at and not (
            timedelta(0) <= self.fetched_at - self.observed_at <= timedelta(hours=2)
        ):
            raise ValueError("Current weather must be recent and cannot be in the future")
        if self.forecast_valid_at and not (
            timedelta(0) < self.forecast_valid_at - self.fetched_at <= timedelta(hours=1)
        ):
            raise ValueError("Probability must describe the hour containing retrieval time")
        return self
