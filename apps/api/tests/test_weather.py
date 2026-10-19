"""Synthetic weather fixtures; all provider calls use httpx.MockTransport."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, get_args

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import ROOT, Settings
from app.integrations.open_meteo import CURRENT_UNITS, OPEN_METEO_URL, OpenMeteoClient
from app.main import create_app
from app.repositories.poi_repository import POIRepository
from app.schemas.weather import WEATHER_TZ, WeatherAnchorID, WeatherResponse
from app.services.weather_service import WeatherService

ANCHOR = "expo_nur_alem"
CURRENT_FIELDS = (
    "temperature_c",
    "apparent_temperature_c",
    "precipitation_mm",
    "wind_speed_kmh",
    "weather_code",
)


class Clock:
    def __init__(self) -> None:
        self.elapsed = 0.0
        self.started = datetime(2026, 10, 19, 21, 5, tzinfo=WEATHER_TZ)

    def monotonic(self) -> float:
        return self.elapsed

    def now(self) -> datetime:
        return self.started + timedelta(seconds=self.elapsed)


@pytest.fixture
def payload() -> dict[str, Any]:
    return {
        "timezone": "Asia/Almaty",
        "utc_offset_seconds": 18000,
        "current_units": {"time": "iso8601", **CURRENT_UNITS},
        "current": {
            "time": "2026-10-19T21:00",
            "temperature_2m": 8.5,
            "apparent_temperature": 5.1,
            "precipitation": 0,
            "wind_speed_10m": 15,
            "weather_code": 3,
        },
        "hourly_units": {"time": "iso8601", "precipitation_probability": "%"},
        "hourly": {
            "time": ["2026-10-19T21:00", "2026-10-19T22:00", "2026-10-19T23:00"],
            "precipitation_probability": [5, 20, 90],
        },
    }


class Harness:
    def __init__(self, payload: dict[str, Any], **config: Any) -> None:
        self.payload = payload
        self.calls: list[httpx.Request] = []
        self.clock = Clock()
        self.delay_seconds = 0.0
        self.error: Exception | None = None
        self.status = 200
        self.content: bytes | None = None
        self.settings = Settings(semantic_enabled=False, llm_provider="disabled", **config)
        self.http = httpx.Client(transport=httpx.MockTransport(self.handle), trust_env=False)
        self.service = WeatherService(
            OpenMeteoClient(self.http, forecast_hours=self.settings.weather_forecast_hours),
            self.settings,
            clock=self.clock.monotonic,
            now=self.clock.now,
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        self.clock.elapsed += self.delay_seconds
        if self.error:
            raise self.error
        if self.content is not None:
            return httpx.Response(self.status, content=self.content)
        return httpx.Response(self.status, json=self.payload)


@pytest.fixture
def harness(payload: dict[str, Any]) -> Harness:
    return Harness(payload)


def assert_unknown(result: WeatherResponse, warning: str) -> None:
    assert result.status == "unknown"
    assert warning in result.warnings
    assert all(getattr(result, field) is None for field in CURRENT_FIELDS)
    assert result.precipitation_probability_percent is None
    assert result.observed_at is None and result.forecast_valid_at is None
    assert result.fetched_at.utcoffset() == timedelta(hours=5)
    assert WeatherResponse.model_validate_json(result.model_dump_json()) == result


def test_units_provenance_and_independent_timestamps(harness: Harness) -> None:
    weather = harness.service.get_weather(ANCHOR)
    assert weather.status == "available"
    assert weather.temperature_c == 8.5 and weather.apparent_temperature_c == 5.1
    assert weather.precipitation_mm == 0 and weather.wind_speed_kmh == 15
    assert weather.weather_code == 3 and weather.precipitation_probability_percent == 20
    assert weather.observed_at == datetime(2026, 10, 19, 21, tzinfo=WEATHER_TZ)
    assert weather.forecast_valid_at == datetime(2026, 10, 19, 22, tzinfo=WEATHER_TZ)
    assert weather.fetched_at == harness.clock.now()
    assert weather.timezone == "Asia/Almaty" and weather.source == "open-meteo"
    request = harness.calls[0]
    assert str(request.url).startswith(OPEN_METEO_URL)
    assert request.url.params["current"] == ",".join(CURRENT_UNITS)
    assert request.url.params["hourly"] == "precipitation_probability"
    for name, value in {
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "timezone": "Asia/Almaty",
        "forecast_hours": "3",
        "timeformat": "iso8601",
    }.items():
        assert request.url.params[name] == value
    assert request.extensions["timeout"]["read"] == 5
    assert "weather_model_estimate_not_station_observation" in weather.warnings


@pytest.mark.parametrize("anchor_id", get_args(WeatherAnchorID))
def test_four_catalog_coordinates(anchor_id: WeatherAnchorID, harness: Harness) -> None:
    result = harness.service.get_weather(anchor_id)
    assert result.anchor_id == anchor_id
    catalog = json.loads((ROOT / "shared/anchors.json").read_bytes())
    point = next(anchor["location"] for anchor in catalog["anchors"] if anchor["id"] == anchor_id)
    for coordinate in ("latitude", "longitude"):
        assert float(harness.calls[0].url.params[coordinate]) == point[coordinate]


def test_cache_hit_expiration_and_mutation_isolation(harness: Harness) -> None:
    first = harness.service.get_weather(ANCHOR)
    first.warnings.append("caller_mutation")
    harness.clock.elapsed = 599
    second = harness.service.get_weather(ANCHOR)
    assert first.cache_status == "miss" and second.cache_status == "hit"
    assert len(harness.calls) == 1 and second.fetched_at == first.fetched_at
    assert "caller_mutation" not in second.warnings
    harness.clock.elapsed = 600
    third = harness.service.get_weather(ANCHOR)
    assert len(harness.calls) == 2 and third.cache_status == "miss"
    assert third.fetched_at > second.fetched_at


def test_expired_cache_never_disguises_failed_refresh(harness: Harness) -> None:
    harness.service.get_weather(ANCHOR)
    harness.clock.elapsed = 600
    harness.error = httpx.ReadTimeout("private diagnostics")
    result = harness.service.get_weather(ANCHOR)
    assert_unknown(result, "weather_timeout")
    assert result.cache_status == "miss" and len(harness.calls) == 2
    assert "private" not in result.model_dump_json()
    assert harness.service.get_weather(ANCHOR).cache_status == "hit"
    harness.clock.elapsed += 30
    harness.error = None
    assert harness.service.get_weather(ANCHOR).status == "available"
    assert len(harness.calls) == 3


def test_bounded_cache_and_forecast_parameter_key(payload: dict[str, Any]) -> None:
    harness = Harness(payload, weather_cache_max_entries=2)
    for anchor in get_args(WeatherAnchorID):
        harness.service.get_weather(anchor)
    assert len(harness.service._cache) == 2
    harness.service.get_weather(ANCHOR)
    assert len(harness.calls) == 5
    harness.service.client = OpenMeteoClient(harness.http, forecast_hours=4)
    harness.service.get_weather(ANCHOR)
    assert len(harness.calls) == 6 and len(harness.service._cache) == 2


def test_concurrent_misses_coalesce(harness: Harness) -> None:
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: harness.service.get_weather(ANCHOR), range(8)))
    assert len(harness.calls) == 1
    assert sum(result.cache_status == "miss" for result in results) == 1


def test_crossing_hour_boundary_refreshes_probability(harness: Harness) -> None:
    harness.clock.started = harness.clock.started.replace(minute=59)
    first = harness.service.get_weather(ANCHOR)
    harness.clock.elapsed = 60
    second = harness.service.get_weather(ANCHOR)
    assert len(harness.calls) == 2
    assert first.precipitation_probability_percent == 20
    assert second.precipitation_probability_percent == 90
    assert second.forecast_valid_at == datetime(2026, 10, 19, 23, tzinfo=WEATHER_TZ)


def test_fetch_time_records_completion(harness: Harness) -> None:
    harness.delay_seconds = 10
    result = harness.service.get_weather(ANCHOR)
    assert result.fetched_at == harness.clock.now()
    harness.clock.elapsed += 599
    assert harness.service.get_weather(ANCHOR).cache_status == "hit"
    assert len(harness.calls) == 1


def test_current_expiring_during_http_request_is_unknown(harness: Harness) -> None:
    harness.payload["current"]["time"] = "2026-10-19T19:05"
    harness.delay_seconds = 1
    assert_unknown(harness.service.get_weather(ANCHOR), "weather_invalid_response")


@pytest.mark.parametrize(
    "error,warning",
    [
        (httpx.ReadTimeout("hidden"), "weather_timeout"),
        (httpx.ConnectTimeout("hidden"), "weather_timeout"),
        (httpx.ConnectError("DNS hidden"), "weather_connection_error"),
        (httpx.RemoteProtocolError("hidden"), "weather_connection_error"),
    ],
)
def test_transport_failures(error: Exception, warning: str, harness: Harness) -> None:
    harness.error = error
    assert_unknown(harness.service.get_weather(ANCHOR), warning)


@pytest.mark.parametrize(
    "status,warning",
    [
        (429, "weather_rate_limited"),
        (500, "weather_upstream_unavailable"),
        (503, "weather_upstream_unavailable"),
        (403, "weather_http_error"),
        (302, "weather_http_error"),
    ],
)
def test_http_failures(status: int, warning: str, harness: Harness) -> None:
    harness.status = status
    assert_unknown(harness.service.get_weather(ANCHOR), warning)
    assert len(harness.calls) == 1


@pytest.mark.parametrize("content", [b"{", b"<html>maintenance</html>", b"\xff"])
def test_invalid_json(content: bytes, harness: Harness) -> None:
    harness.content = content
    assert_unknown(harness.service.get_weather(ANCHOR), "weather_invalid_json")


@pytest.mark.parametrize("value", [-1, 101, float("nan"), float("inf"), "20", True])
def test_invalid_probability(value: Any, harness: Harness) -> None:
    harness.payload["hourly"]["precipitation_probability"][1] = value
    # Send raw JSON so the NaN/Infinity rejection is tested in our adapter, not httpx's encoder.
    harness.content = json.dumps(harness.payload).encode()
    assert_unknown(harness.service.get_weather(ANCHOR), "weather_invalid_response")


@pytest.mark.parametrize("value", [0, 100])
def test_probability_boundaries(value: int, harness: Harness) -> None:
    harness.payload["hourly"]["precipitation_probability"][1] = value
    assert harness.service.get_weather(ANCHOR).precipitation_probability_percent == value


@pytest.mark.parametrize(
    "field,value",
    [
        ("temperature_2m", "8.5"),
        ("temperature_2m", True),
        ("temperature_2m", float("nan")),
        ("temperature_2m", float("inf")),
        ("temperature_2m", -101),
        ("precipitation", -1),
        ("wind_speed_10m", -1),
        ("weather_code", 100),
        ("weather_code", 4),
        ("weather_code", True),
        ("weather_code", 3.0),
        ("weather_code", "3"),
    ],
)
def test_invalid_current_values(field: str, value: Any, harness: Harness) -> None:
    harness.payload["current"][field] = value
    harness.content = json.dumps(harness.payload).encode()
    assert_unknown(harness.service.get_weather(ANCHOR), "weather_invalid_response")


@pytest.mark.parametrize("field", list(CURRENT_UNITS))
@pytest.mark.parametrize("missing", [True, False])
def test_missing_individual_indicators(field: str, missing: bool, harness: Harness) -> None:
    if missing:
        harness.payload["current"].pop(field)
    else:
        harness.payload["current"][field] = None
    result = harness.service.get_weather(ANCHOR)
    assert result.status == "available" and "weather_current_incomplete" in result.warnings
    target = {
        "temperature_2m": "temperature_c",
        "apparent_temperature": "apparent_temperature_c",
        "precipitation": "precipitation_mm",
        "wind_speed_10m": "wind_speed_kmh",
        "weather_code": "weather_code",
    }[field]
    assert getattr(result, target) is None


@pytest.mark.parametrize(
    "hourly",
    [
        None,
        {"time": [], "precipitation_probability": []},
        {"time": ["2026-10-19T22:00"]},
        {"time": ["2026-10-19T22:00"], "precipitation_probability": [None]},
        {"time": ["2026-10-19T20:00"], "precipitation_probability": [10]},
        {"time": ["2026-10-19T23:00"], "precipitation_probability": [10]},
    ],
)
def test_missing_or_nonmatching_hourly(hourly: Any, harness: Harness) -> None:
    harness.payload["hourly"] = hourly
    result = harness.service.get_weather(ANCHOR)
    assert result.status == "available" and result.temperature_c == 8.5
    assert result.precipitation_probability_percent is None and result.forecast_valid_at is None
    assert "weather_hourly_probability_unavailable" in result.warnings


@pytest.mark.parametrize(
    "section,stamp",
    [
        ("current", "broken"),
        ("current", "2026-10-19"),
        ("current", "2026-10-19T21:00:00+06:00"),
        ("current", "2026-10-19T21:00:00Z"),
        ("current", "2026-10-19T21:15"),
        ("current", "2026-10-19T18:00"),
        ("current", "2026-02-30T21:00"),
        ("hourly", "2026-10-19T22:15"),
        ("hourly", "2026-10-19T21:00"),
        ("hourly", "broken"),
        ("hourly", "2026-10-19T22:00+06:00"),
    ],
)
def test_invalid_timestamps(section: str, stamp: str, harness: Harness) -> None:
    if section == "current":
        harness.payload[section]["time"] = stamp
    else:
        harness.payload[section]["time"][1] = stamp
    assert_unknown(harness.service.get_weather(ANCHOR), "weather_invalid_response")


def test_explicit_correct_timestamp_offset(harness: Harness) -> None:
    harness.payload["current"]["time"] += ":00+05:00"
    assert harness.service.get_weather(ANCHOR).status == "available"


@pytest.mark.parametrize(
    "mutation",
    [
        "timezone",
        "offset",
        "missing_timezone",
        "missing_time",
        "units",
        "missing_units",
        "hourly_units",
        "array_length",
        "duplicate_hours",
        "backwards_hours",
        "null_array",
    ],
)
def test_invalid_metadata_and_arrays(mutation: str, harness: Harness) -> None:
    data = harness.payload
    if mutation == "timezone":
        data["timezone"] = "Asia/Unknown"
    elif mutation == "offset":
        data["utc_offset_seconds"] = 21600
    elif mutation == "missing_timezone":
        data.pop("timezone")
    elif mutation == "missing_time":
        data["current"].pop("time")
    elif mutation == "units":
        data["current_units"]["temperature_2m"] = "°F"
    elif mutation == "missing_units":
        data.pop("current_units")
    elif mutation == "hourly_units":
        data["hourly_units"]["precipitation_probability"] = "fraction"
    elif mutation == "array_length":
        data["hourly"]["precipitation_probability"].pop()
    elif mutation == "duplicate_hours":
        data["hourly"]["time"][2] = data["hourly"]["time"][1]
    elif mutation == "backwards_hours":
        data["hourly"]["time"].reverse()
    elif mutation == "null_array":
        data["hourly"]["time"] = None
    assert_unknown(harness.service.get_weather(ANCHOR), "weather_invalid_response")


@pytest.mark.parametrize("raw", [None, [], {}, {"error": True, "reason": "private"}])
def test_invalid_payload_shape(raw: Any, harness: Harness) -> None:
    harness.content = json.dumps(raw).encode()
    assert_unknown(harness.service.get_weather(ANCHOR), "weather_invalid_response")


def test_empty_evidence_is_unknown(harness: Harness) -> None:
    harness.payload["current"] = None
    harness.payload["hourly"] = None
    assert_unknown(harness.service.get_weather(ANCHOR), "weather_conditions_unknown")


def test_forecast_only_preserves_current_as_unknown(harness: Harness) -> None:
    harness.payload.pop("current")
    result = harness.service.get_weather(ANCHOR)
    assert result.status == "available" and result.precipitation_probability_percent == 20
    assert result.observed_at is None and result.temperature_c is None
    assert "weather_current_incomplete" in result.warnings


def test_assessment_thresholds_and_missing_values(harness: Harness) -> None:
    harness.payload["current"].update(apparent_temperature=0, wind_speed_10m=35, precipitation=2)
    harness.payload["hourly"]["precipitation_probability"][1] = 70
    result = harness.service.get_weather(ANCHOR)
    assert set(result.warnings) >= {
        "weather_low_temperature",
        "weather_strong_wind",
        "weather_significant_precipitation",
        "weather_high_precipitation_probability",
    }
    other = Harness(
        copy.deepcopy(harness.payload),
        weather_wind_kmh=36,
        weather_cold_c=-1,
        weather_precipitation_mm=3,
        weather_precipitation_probability=71,
    )
    assert other.service.get_weather(ANCHOR).warnings == [
        "weather_model_estimate_not_station_observation"
    ]


def test_schema_and_no_gps_api(harness: Harness, repository: POIRepository) -> None:
    app = create_app(harness.settings, repository, weather_service=harness.service)
    with TestClient(app) as client:
        response = client.get("/api/v1/weather", params={"start_anchor_id": ANCHOR})
        assert response.status_code == 200
        assert WeatherResponse.model_validate(response.json()).status == "available"
        for params in (
            {},
            {"start_anchor_id": "unknown"},
            {"start_anchor_id": ANCHOR, "latitude": "51", "longitude": "71"},
            {"start_anchor_id": ANCHOR, "gps": "51,71"},
            {"start_anchor_id": ANCHOR, "forecast_hours": "48"},
        ):
            invalid = client.get("/api/v1/weather", params=params)
            assert invalid.status_code == 422
            assert all("input" not in item for item in invalid.json()["detail"])
        schema = client.get("/openapi.json").json()
        operation = schema["paths"]["/api/v1/weather"]["get"]
        assert [param["name"] for param in operation["parameters"]] == ["start_anchor_id"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/WeatherResponse"
        }
        assert schema["components"]["schemas"]["WeatherResponse"]["additionalProperties"] is False
    assert len(harness.calls) == 1


def test_unknown_anchor_direct_service(harness: Harness) -> None:
    with pytest.raises(ValueError, match="Unknown weather anchor"):
        harness.service.get_weather("unknown")  # type: ignore[arg-type]
    assert not harness.calls


def test_provider_failure_does_not_break_other_endpoints(
    harness: Harness, repository: POIRepository
) -> None:
    harness.error = httpx.ConnectError("offline")
    with TestClient(
        create_app(harness.settings, repository, weather_service=harness.service)
    ) as api:
        weather = api.get("/api/v1/weather", params={"start_anchor_id": ANCHOR})
        assert weather.status_code == 200
        assert_unknown(WeatherResponse.model_validate(weather.json()), "weather_connection_error")
        assert api.get("/health").json() == {"status": "ok"}
        assert api.get("/api/v1/pois").json()["total"] == 497
        assert api.post("/api/v1/retrieval/search", json={"query": "Rafe"}).json()["results"]
        rag = api.post("/api/v1/rag/query", json={"query": "Rafe"}).json()
        assert rag["generation_status"] == "retrieval_only"
        route = api.post(
            "/api/v1/routes/plan",
            json={"start_anchor_id": ANCHOR, "duration_minutes": 60, "query": "EXPO"},
        )
        assert route.status_code == 200 and route.json()["status"] == "no_route"
        assert route.json()["reason"] == "ors_unconfigured"


@pytest.mark.parametrize(
    "mutation",
    [
        {"temperature_c": float("nan")},
        {"temperature_c": "8.5"},
        {"precipitation_probability_percent": 101},
        {"fetched_at": "2026-10-19T21:05:00"},
        {"fetched_at": "2026-10-19T21:05:00+06:00"},
        {"observed_at": None},
        {"status": "unknown"},
        {"forecast_valid_at": None},
        {"latitude": 51},
    ],
)
def test_strict_public_response(mutation: dict[str, Any], harness: Harness) -> None:
    result = harness.service.get_weather(ANCHOR).model_dump(mode="json")
    result.update(mutation)
    with pytest.raises(ValidationError):
        WeatherResponse.model_validate(result)


def test_committed_schema_matches() -> None:
    assert json.loads((ROOT / "contracts/weather.schema.json").read_bytes()) == (
        WeatherResponse.model_json_schema()
    )
