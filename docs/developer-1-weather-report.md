# Open-Meteo delivery — Developer №3 handoff

Implemented on `feature/geo-weather`, created from freshly fetched `origin/main`
at `b964b67`. GitHub verification found PR #8 already merged before this work
started. No Route Planner implementation or route schemas were changed.

## Delivered contract

`GET /api/v1/weather?start_anchor_id=expo_nur_alem` serves the four anchors loaded
from `shared/anchors.json`, rejects extra query fields/GPS and unknown IDs with
422, and returns a strict `WeatherResponse`. HTTP/upstream validation failures
return HTTP 200 with `status=unknown`, null weather evidence and safe warnings.
Missing individual indicators remain null in otherwise available responses.

`WeatherService.get_weather(anchor_id)` is ready for direct backend consumption.
Use FastAPI's `get_weather_service` dependency to share the application instance;
the current planner remains independent. The
[frontend guide](developer-3-api-integration.md#weather) includes `fetch()`,
nullable field handling, warning meanings and attribution. The
[backend README](../apps/api/README.md#open-meteo-weather) documents configuration,
model/current versus hourly semantics and operational limits. Runtime
`/openapi.json` includes the endpoint and response; the committed standalone
contract is [weather.schema.json](../contracts/weather.schema.json).

## Executed verification

All commands below were run with Python 3.11. Windows non-ASCII checkout paths
require `PYTHONUTF8=1` and the `PYTHONPATH` documented in the backend README.

| Check | Result |
| --- | --- |
| `cd apps/api; uv sync --python 3.11` | Passed; `tzdata` added for IANA timezone support |
| `uv run pytest -q` | 261 passed, including 103 weather cases |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed, 47 files |
| `uv run mypy app scripts` | Passed, 39 source files |
| Geo tests, separate pytest invocation | 101 passed |
| Data pipeline tests, separate pytest invocation | 39 passed |
| Root `tests/integration`, separate pytest invocation | 36 passed |
| `uv run python scripts/smoke.py` with models disabled | Real Uvicorn health/docs/OpenAPI, 497 POIs, retrieval and RAG passed |
| `uv run python scripts/weather_smoke.py --all-anchors --output examples/weather-live.json` | Real Open-Meteo responses and immediate cache check passed for all four anchors |

Total: 437 passing cases across four separate pytest suites. An initial combined
Geo/Data collection encountered the existing `from conftest import NOW` module
name collision; running the packages separately resolved collection without
changes to their tests. Backend pytest reports two dependency deprecation
warnings from Starlette/httpx and AnyIO; no failures.

Weather tests are offline: every upstream call uses `httpx.MockTransport`, and the
existing autouse network blocker is active. Coverage includes timeout, DNS/other
transport failures, 429, 5xx, redirects, invalid JSON/schema, units, missing data,
NaN/Infinity, strict numeric/WMO values, timezone and timestamp errors, mismatched
arrays, all anchors, schema drift/OpenAPI, public GPS rejection and endpoint
regressions after a weather provider failure.

TTL checks use injected monotonic/wall clocks, without sleeping: an initial miss
makes one HTTP call; at 599 seconds the next call is a hit with the original
`fetched_at`; at 600 seconds it refreshes. After expiry, a failed refresh returns
unknown rather than cached weather. Failure TTL expires after 30 seconds. Tests
also cover LRU bounds, parameter-sensitive keys, simultaneous miss coalescing,
caller mutation isolation, hour-boundary refresh, fetch completion timestamps,
and data becoming too old while the HTTP request is in flight.

## Recorded real response

This is a historical response from the live run on 19 October 2026, **not a
fixture, default, or current forecast**. The complete four-anchor output is in
[weather-live.json](../apps/api/examples/weather-live.json).

```json
{
  "status": "available",
  "anchor_id": "expo_nur_alem",
  "temperature_c": 10.3,
  "apparent_temperature_c": 5.2,
  "precipitation_mm": 0.0,
  "precipitation_probability_percent": 0.0,
  "wind_speed_kmh": 21.0,
  "weather_code": 3,
  "timezone": "Asia/Almaty",
  "observed_at": "2026-10-19T22:45:00+05:00",
  "forecast_valid_at": "2026-10-19T23:00:00+05:00",
  "fetched_at": "2026-10-19T22:50:35.946573+05:00",
  "source": "open-meteo",
  "cache_status": "miss",
  "warnings": ["weather_model_estimate_not_station_observation"]
}
```

## Changed files

- `.env.example`
- `README.md`
- `apps/api/.env.example`
- `apps/api/README.md`
- `apps/api/app/core/config.py`
- `apps/api/app/main.py`
- `apps/api/app/integrations/open_meteo.py`
- `apps/api/app/routers/weather.py`
- `apps/api/app/schemas/weather.py`
- `apps/api/app/services/weather_service.py`
- `apps/api/examples/weather-live.json`
- `apps/api/scripts/weather_smoke.py`
- `apps/api/tests/test_weather.py`
- `apps/api/pyproject.toml`
- `apps/api/uv.lock`
- `contracts/weather.schema.json`
- `docs/developer-3-api-integration.md`
- `docs/developer-1-weather-report.md`

## Operational limits

The cache is per process, bounded to four entries, and successful entries expire
after 10 minutes or earlier at the probability interval/current freshness boundary.
Failures are cached for 30 seconds. There is no stale fallback, shared worker
cache, global rate limiter, automatic provider retry, or persistent weather store.
One lock coalesces concurrent misses and serializes weather calls across anchors.
HTTP timeout bounds individual network operations, not a whole multi-request walk.

Open-Meteo current conditions are model estimates; probability describes the
preceding hour ending at `forecast_valid_at`. Model grid cells can be shared
between nearby anchors. Product thresholds (wind 35 km/h, current-step
precipitation 2 mm, feels-like/air temperature 0 °C, hourly probability 70%) are
configurable heuristics, not official danger criteria. Missing indicators and an
empty heuristic assessment cannot establish safe walking conditions. Current
precipitation is a model-step amount, typically 15 minutes, not a one-hour total.
No ORS time, route geometry or route budget is modified. See the
[official forecast definitions](https://open-meteo.com/en/docs).

Developer №3 can integrate the endpoint immediately. Future backend composition
can call the typed shared service without an HTTP self-call; actual planner
policy changes belong in a separate change. No repository secrets or local
`.env` were included in the changes.
