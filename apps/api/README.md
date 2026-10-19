# VibeRoute backend

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required. From the repository root:

```sh
cd apps/api
uv sync --python 3.11
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

On Windows with Python 3.11 and a non-ASCII checkout path, set these from
`apps/api` in PowerShell before running the commands above:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH='.;../../packages/geo/src;../../packages/data_pipeline/src;../..'
```

Python 3.11 reads editable-install `.pth` paths using the Windows locale even
in UTF-8 mode. Explicit source paths avoid this import problem; UTF-8 mode also
keeps console output and subprocess text consistent.

The source checkout must include `data/astana/pois.json`. Local editable dependencies
resolve from `packages/data_pipeline` and `packages/geo`. POI lookup and lexical
retrieval need no external service. Route planning needs ORS and a server-side key.
Startup fails clearly if Dataset validation
fails; the file is loaded once and indexed by unique ID. Restart to load a new snapshot.
No modifications to the dataset or geographic packages are made by this backend.

Environment configuration (no automatic `.env` reading):

| Variable | Default | Purpose |
| --- | --- | --- |
| `POI_DATASET_PATH` | checkout `data/astana/pois.json` | Explicit snapshot path |
| `CORS_ORIGINS` | `[]` | JSON array of exact frontend origins |

For local frontend work set `CORS_ORIGINS='["http://localhost:3000"]'` (PowerShell:
`$env:CORS_ORIGINS='["http://localhost:3000"]'`). Wildcards are rejected. Configure
production origins explicitly. Bind behind an appropriately configured reverse proxy
when deployed; this development server has no user accounts or rate limiter.
Do not enable query/body logging: text can contain private location information.
The suggested Uvicorn command disables access logs for this reason.

## API integration for Developer №3

Interactive docs: <http://127.0.0.1:8000/docs>; machine schema: `/openapi.json`.

```sh
curl http://127.0.0.1:8000/health
curl 'http://127.0.0.1:8000/api/v1/pois?q=Rafe&category=cafe&limit=2&offset=0'
curl http://127.0.0.1:8000/api/v1/pois/osm:node:1843876259
```

Health returns `{"status":"ok"}` after successful startup. Search returns
`{"items":[...],"total":1,"limit":2,"offset":0,"dataset":{...}}` for the Rafe
query in the committed snapshot. `total` counts matches before pagination. Results
are ordered by stable ID, with NFKC/casefold substring search in real names,
localized OSM names, categories and addresses. `q` ≤200 characters; `limit` 1–100;
`offset` 0–100000. Category is an OpenAPI enum. Invalid parameters return 422 with
locations and safe messages; unknown IDs return 404; no matches return an empty list.
Consumers must use server IDs and handle `null` and empty lists without fabrication.
There is no raw GPS endpoint and no implicit proximity or walking calculation.

## Public POI contract

[`../../contracts/poi.schema.json`](../../contracts/poi.schema.json) is generated from
`app.schemas.poi.PublicPOI.model_json_schema()`; tests detect drift. Internal fields
map as follows:

| Public field | Dataset source |
| --- | --- |
| `id`, `name`, `category`, `opening_hours`, `quality_warnings` | unchanged POI fields |
| `latitude`, `longitude`, `coordinate_kind` | `coordinates.latitude/longitude/kind` |
| `address` | `address` dictionary, empty dictionary becomes `null` |
| `indoor`, `covered`, `wheelchair` | `attributes`, preserving `null` |
| `source_url`, `retrieved_at` | `provenance.url/retrieved_at` |
| `provenance` | complete original provenance, including version/time/field tags |
| `source` | dataset OSM attribution, ODbL-1.0 and copyright URL |
| `verification_status` | `osm_source_only`: no independent field verification |

List metadata includes the SHA-256 of the exact dataset bytes, capture hash,
collection/base timestamps, endpoint and schema version. Bounding-box centers are
representative points, not verified entrances. Hours are source text, not a current
open/closed verdict. OSM statements may be stale or wrong; missing evidence stays
unknown. Display attribution and retain ODbL metadata when redistributing records.

## Checks

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

Tests use the committed 497 real POIs and no network. Route tests inject a fake
GeoAdapter or HTTP MockTransport; their synthetic geometry is only a test fixture.
POI search does not call ORS.

## Retrieval and local Qwen

`POST /api/v1/retrieval/search` and `POST /api/v1/rag/query` accept
`{"query":"Ботаникалық бақ","top_k":5,"language":"kk"}`. The query is limited
to 1000 characters, `top_k` to 1–10, and the JSON body to 16 KiB. Language is
optional (`ru`, `kk`, `en`); short ambiguous phrases can use an explicit language.
See the [Developer №3 integration guide](../../docs/developer-3-api-integration.md)
for full response examples and fallback handling, and the
[retrieval architecture](../../docs/retrieval-rag.md) for grounding guarantees.

The default search is BM25, explicitly reported as `lexical`. To run entirely
without models, export `LLM_PROVIDER=disabled` and `SEMANTIC_ENABLED=false`.
Normal POI API startup never contacts Overpass or ORS. Semantic indexing contacts
only the configured embedding service when explicitly enabled.

Install [Ollama](https://ollama.com/) and pull the exact models:

```sh
ollama pull qwen3:4b-instruct
ollama pull qwen3-embedding:0.6b
```

Export variables shown in [.env.example](.env.example), or copy it to `.env` and
explicitly load it using `uv run uvicorn app.main:app --env-file .env --no-access-log`.
No `.env` is read implicitly. The required model identifiers are configurable:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen3:4b-instruct
EMBEDDING_MODEL=qwen3-embedding:0.6b
SEMANTIC_ENABLED=true
```

Before starting the server, warm the index (optional):

```sh
uv run python scripts/build_index.py
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In PowerShell use `$env:SEMANTIC_ENABLED='true'` and `$env:LLM_PROVIDER='ollama'`.
Index files default to ignored `data/tmp/embeddings`, separate from source POIs.
An unavailable embedding model produces `retrieval_mode=lexical` and a warning;
an unavailable or invalid LLM produces `generation_status=retrieval_only`.
Neither condition makes the POI API unavailable. Restart to retry an index build
that failed at startup; a failed query embedding is retried on the next request.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SEMANTIC_ENABLED` | `false` | Explicit embedding/index opt-in |
| `LLM_PROVIDER` | `ollama` | `ollama` or `disabled` |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Server-side provider endpoint |
| `EMBEDDING_MODEL` | `qwen3-embedding:0.6b` | Cache model identifier |
| `LLM_MODEL` | `qwen3:4b-instruct` | Chat model |
| `EMBEDDING_INDEX_DIR` | checkout `data/tmp/embeddings` | Derived cache directory |
| `EMBEDDING_BATCH_SIZE` | `32` | 1–128 source documents per embed call |
| `EMBEDDING_TIMEOUT_SECONDS` | `60` | Per-call timeout, max 120 |
| `INDEX_BUILD_TIMEOUT_SECONDS` | `300` | Deadline checked between batches, max 600 |
| `LLM_TIMEOUT_SECONDS` | `60` | Per-call timeout, max 120 |
| `LLM_MAX_TOKENS` | `1200` | 100–4096 output tokens, temperature zero |
| `SEMANTIC_MIN_SCORE` | `0.35` | Cosine candidate threshold, not factual confidence |
| `CONTEXT_MAX_BYTES` | `24000` | UTF-8 evidence limit, 1024–64000 |

The index deadline may be exceeded by at most one in-flight request timeout.
Cold model loads and CPU indexing can take minutes; the explicit build command
keeps that cost out of application readiness. No call retries indefinitely.

Additional checks:

```sh
uv run mypy app scripts
uv run python scripts/smoke.py
uv run python scripts/ollama_smoke.py
```

`smoke.py` starts a real local Uvicorn server with the current environment.
For a reproducible model-free smoke set `LLM_PROVIDER=disabled` and
`SEMANTIC_ENABLED=false`. `ollama_smoke.py` requires both real models, verifies
hybrid retrieval and grounded Kazakh output, returns 0 on success, 1 on failure,
and 2 when skipped because a model/service is unavailable. Mock unit tests never
use the network; real-model success is reported separately.

## Walking route planner

`POST /api/v1/routes/plan` accepts an anchor ID, never user GPS coordinates:

```sh
curl -X POST http://127.0.0.1:8000/api/v1/routes/plan \
  -H 'Content-Type: application/json' \
  -d '{"start_anchor_id":"expo_nur_alem","duration_minutes":60,"query":"Хочу спокойную прогулку возле EXPO","round_trip":true,"language":"ru"}'
```

Set `ORS_API_KEY` in the server environment, or load a local ignored `.env`
explicitly with `uv run uvicorn app.main:app --env-file ../../.env --no-access-log`.
Never send the key from the frontend. No key is needed to start the API; the
planner returns `status=no_route`, `reason=ors_unconfigured` when it is missing.
The anchor catalog is loaded from `shared/anchors.json` at startup.

| Variable | Default | Meaning |
| --- | --- | --- |
| `ORS_API_KEY` | unset | Server-side credential, stored as `SecretStr` |
| `ORS_BASE_URL` | `https://api.heigit.org/openrouteservice` | HTTPS provider base URL |
| `ORS_TIMEOUT_SECONDS` | `10` | Per HTTP operation timeout, 1–60 s; connect timeout ≤5 s |
| `ROUTE_MAX_CANDIDATES` | `10` | 1–10 POIs passed to Matrix, plus the start |
| `ROUTE_NEARBY_RADIUS_M` | `2500` | Straight-line filtering radius, 100–10000 m |
| `ROUTE_SNAP_RADIUS_M` | `100` | Maximum accepted snapping distance, 1–1000 m |

The four IDs are `mega_silk_way`, `botanical_garden`, `expo_nur_alem`, and
`nurzhol_boulevard`. Duration must be a JSON integer from 30 through 180;
`round_trip` a JSON boolean (default `true`); query nonblank, ≤1000 characters;
language `ru|kk|en` (default `ru`). Extra fields and raw GPS are rejected with 422.
The existing 16 KiB body limit applies.

Planning reuses RetrievalService (hybrid when enabled, lexical on embedding
failure), then filters geographically. If fewer than three local hits exist,
at most three total candidates are filled from the nearest real POIs, with
explicit `nearby_fallback` selection and warnings. Source text is never executed
or fed into generation. No LLM is required or called by the planner.

Directed ORS Matrix edges determine reachability and greedy selection of at
most three stops. Missing durations/distances, unsnapped points and excessive
snap offsets cannot form a leg. Each selection reserves visits and, for a round
trip, the return leg. Final ORS Directions geometry and summary determine public
walking time/distance. Directions waypoints must match the requested locations
within the configured snap radius (plus 1 m tolerance). If the final duration
exceeds the budget, the last stop is removed and Directions is tried once more.
A remaining overrun or any provider failure yields `no_route`, never a straight
line or Haversine walking estimate. The heuristic is conservative and does not
guarantee an optimal route or discover every feasible stop sequence.

Each plan makes ≤1 Matrix and ≤2 Directions adapter calls. The unchanged
GeoAdapter retries transport/429/502/503/504 failures up to three attempts per
call, so ≤9 HTTP attempts; retry backoff/Retry-After can add up to 60 s per call.
This is a per-plan bound, not a global rate limiter. Matrix timeouts are normalized
by the adapter to `ors_unavailable` plus `ors_transport_error`; directly raised
timeouts produce `ors_timeout`. Provider diagnostics and secrets are not returned.

`success` includes real POI IDs, ordered stops, complete OSM provenance, original
validated ORS GeoJSON and both Matrix/Directions provenance. `no_route` is HTTP
200 with an explicit reason and localized recommendation; its geometry and all
time/distance fields are `null`, and stops are empty. See the
[frontend guide](../../docs/developer-3-api-integration.md#walking-route-planner)
for `fetch()`, mapping and error handling. `/docs` describes the discriminated
response union. Invalid requests return 422; oversized bodies return 413.

Visit allowances by source category (minutes, not measured durations):

| Minutes | Categories |
| --- | --- |
| 5 | artwork, viewpoint |
| 10 | fast_food, community_centre, attraction, park, garden, playground, books |
| 15 | cafe, food_court, library, cinema, theatre, arts_centre, gallery, mall |
| 20 | restaurant, museum |

These allowances do not include a whole cinema/theatre performance and do not
promise admission. Unknown hours/accessibility remain `null`. Bounding-box
centers (including EXPO and Botanical Garden anchors) are not verified entrances;
the corresponding IDs appear in warnings. ORS confirms a graph path, not current
opening, legal entry, wheelchair access, quietness or Wi-Fi. Weather is available
through the independent service below; the planner does not consume it yet. H3
remains separate work.

Optional live smoke (separate from unit tests; requires `ORS_API_KEY`):

```sh
uv run python scripts/routes_smoke.py
```

It makes one plan through the real adapter, validates geometry/budget/source IDs
and prints only non-secret summary metrics. Exit 0 means a live route passed;
1 means failure or `no_route`; 2 means skipped because no key was available.

## Open-Meteo weather

```sh
curl 'http://127.0.0.1:8000/api/v1/weather?start_anchor_id=expo_nur_alem'
uv run python scripts/weather_smoke.py --all-anchors
```

This endpoint accepts only the four catalog anchor IDs; unknown IDs, missing IDs
and extra query fields (including GPS) return 422. Coordinates come exclusively
from `shared/anchors.json`, loaded once when WeatherService is created. No API key
is required for this non-commercial MVP. No weather call occurs during startup,
POI search, RAG, or route planning. Only the explicit weather request calls
`https://api.open-meteo.com/v1/forecast`. The managed HTTP client closes at shutdown.

`OpenMeteoClient` handles HTTP, timeout and strict upstream validation;
`WeatherService.get_weather(anchor_id)` returns `WeatherResponse` directly for
future Route Planner use without HTTP self-calls. FastAPI exposes the same service
through DI (`get_weather_service`) and `create_app(weather_service=...)` supports
injected test instances. The existing planner and its ORS times are unchanged.

Current model fields use °C, mm, km/h and WMO codes. `observed_at` identifies the
current **model estimate**, not a station measurement. Hourly precipitation
probability uses percent and its own `forecast_valid_at`: the end of the hour
containing `fetched_at`, since Open-Meteo defines probability over the preceding
hour. For example, retrieval at 21:05 selects the probability ending at 22:00;
it is never reported as a 21:00 current measurement. At exactly 22:00 the next
interval ending at 23:00 is selected. Times include the `Asia/Almaty` offset;
`tzdata` supplies IANA rules on Windows. Requests ask for five current indicators
and only hourly probability, over three hourly steps by default.

Successful partial data retain missing indicators as `null`, with warnings.
If no usable indicator exists or the response is malformed/unavailable, HTTP 200
returns `status=unknown`, null indicators/timestamps, safe warning codes and the
fetch-attempt time. NaN/Infinity, numeric strings/booleans, invalid units, WMO codes,
timezone/offsets, dates and mismatched hourly arrays are rejected. Current model
data older than two hours or in the future are rejected. A missing or empty hourly
forecast leaves probability/time null and preserves valid current indicators.
Provider bodies, URLs and diagnostics never enter the public warnings.

The per-process memory cache uses a monotonic 600-second TTL, capped at four LRU
entries. Keys include anchor ID, catalog coordinates, fields, units, timezone and
forecast horizon. Concurrent misses are coalesced by a lock; weather calls for
different anchors are also serialized in this MVP. Current data freshness and
the hourly interval boundary can expire an entry before its TTL. Expired entries
are discarded before refresh; a failed refresh returns unknown, with no stale
weather fallback. Unknown responses are cached for 30 seconds to avoid retry
storms. Cache hits retain original `fetched_at` and evidence timestamps. Workers
have independent caches; there is no persistence or distributed rate limiter.

| Variable | Default | Meaning |
| --- | --- | --- |
| `WEATHER_TIMEOUT_SECONDS` | `5` | HTTP operation timeout, >0–30 s; connect ≤3 s, no retries |
| `WEATHER_FORECAST_HOURS` | `3` | 2–6 hourly steps from the current hour |
| `WEATHER_CACHE_TTL_SECONDS` | `600` | Successful response TTL, >0–3600 s |
| `WEATHER_FAILURE_TTL_SECONDS` | `30` | Unknown response TTL, >0–60 s |
| `WEATHER_CACHE_MAX_ENTRIES` | `4` | 1–4 entries per service instance |
| `WEATHER_WIND_KMH` | `35` | Warn when current wind ≥35 km/h |
| `WEATHER_PRECIPITATION_MM` | `2` | Warn when current-step precipitation ≥2 mm |
| `WEATHER_COLD_C` | `0` | Warn when feels-like (or temperature if absent) ≤0 °C |
| `WEATHER_PRECIPITATION_PROBABILITY` | `70` | Warn when hourly precipitation probability ≥70% |

These configurable thresholds are **product heuristics**, not official hazardous
weather criteria or a guarantee of walking safety. Current precipitation is the
amount over the provider's current model step (typically 15 minutes), not an
hourly total or rain rate. No warning is inferred from a missing indicator.
Empty warning assessments do not imply good weather. Forecast grid cells can be
shared by nearby anchors and cannot resolve individual paths. Display
[Open-Meteo attribution](https://open-meteo.com/) and consult the
[official forecast definitions](https://open-meteo.com/en/docs).

Public JSON schema: [`contracts/weather.schema.json`](../../contracts/weather.schema.json),
with drift checks; the endpoint is also generated into `/openapi.json` and `/docs`.
The frontend guide documents every warning code. All unit tests use HTTP
MockTransport and injected clocks, without real network or TTL sleeps. The
optional smoke validates the real endpoint, provenance, all anchors when requested,
and immediate cache hits, without fixed expected weather; exit 0 means all
requested anchors passed, 1 means failure/unknown. `--output path.json` records the
actual responses. A full historical sample is in
[`examples/weather-live.json`](examples/weather-live.json); never display it as current weather.
