# Backend integration — Developer №3

Start the service with the commands in [apps/api/README.md](../apps/api/README.md).
Use `http://127.0.0.1:8000` locally and configure `CORS_ORIGINS` to the exact
frontend origin. Read `/openapi.json` for all types or `/docs` for interactive
requests. JSON is UTF-8; use actual OSM IDs instead of deriving IDs from names.
Route planning starts from a catalog anchor; there is no raw user-GPS input field.

## POI lookup

```http
GET /health
GET /api/v1/pois?q=Rafe&category=cafe&limit=20&offset=0
GET /api/v1/pois/osm:node:1843876259
```

Health returns `{"status":"ok"}`. POI search returns `items`, `total`, `limit`,
`offset`, `dataset`. Detail returns a public POI object. The
[public JSON schema](../contracts/poi.schema.json) and backend README document
the mapping from the original dataset. All 497 records are available; no matches
return `items: []`. Unknown IDs return 404 and invalid parameters return 422.
Ordering is stable by ID; search is a normalized substring search, not ranking.

## Retrieval

```js
const response = await fetch(`${apiBase}/api/v1/retrieval/search`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'Хочу кафе возле EXPO с Wi-Fi', top_k: 5, language: 'ru' }),
});
if (!response.ok) throw new Error(`Search failed: ${response.status}`);
const result = await response.json();
```

Shared request body: `query` is 1–1000 characters (non-whitespace), `top_k` is
1–10 (default 5), `language` is optional `ru|kk|en`. Unknown properties are
rejected: do not send latitude/longitude. Bodies over 16 KiB return 413.

The retrieval response has these fields:

| Field | Meaning |
| --- | --- |
| `query` | Original Unicode query |
| `retrieval_mode` | `lexical` (BM25) or `hybrid` (BM25 + embeddings + RRF) |
| `results` | Ranked hits: public `poi`, 1-based `rank`, `score`, component scores, warnings |
| `dataset` | Dataset hash, collection/capture provenance and OSM/ODbL metadata |
| `warnings` | Disabled/unavailable providers and factual limitations |

Component scores are nullable. BM25 and RRF scores have different scales;
neither is a probability or independent verification. `results: []` is normal.
For complete real-snapshot output see
[retrieval-rafe.json](../apps/api/examples/retrieval-rafe.json).

## RAG

```js
const response = await fetch(`${apiBase}/api/v1/rag/query`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'Ботаникалық бақ', top_k: 3, language: 'kk' }),
});
const result = await response.json();
```

The RAG response includes:

| Field | Meaning |
| --- | --- |
| `query`, `language`, `explanation` | Original query and safe localized summary |
| `mentioned_poi_ids` | IDs selected for display; each is in retrieved context |
| `recommendations` | `poi_id` and validated localized explanation per result |
| `sources` | Selected evidence with source URLs, retrieval times and unknown values |
| `generation_status` | `generated` or `retrieval_only` |
| `generation_method` | `constrained_extractive` or `deterministic` |
| `llm_model` | Attempted model, or `null` when no model was called |
| `warnings` | Generation/retrieval fallback and factual limitations |
| `retrieval` | Full retrieval response, including public POIs and original provenance |

The model chooses evidence-backed records and copies server-approved explanation
text. `generated` does not mean the facts were independently verified. If the
provider times out, is unavailable or emits invalid/ungrounded output, display
the safe `retrieval_only` answer normally and make its status visible. A non-null
`llm_model` with `retrieval_only` indicates an attempted but rejected/failed call.
With no evidence, recommendations and sources are empty and no model is called.
See [rag-botanical-kk.json](../apps/api/examples/rag-botanical-kk.json) for a
complete real-record response generated with models disabled.

Key machine-readable warnings include `semantic_disabled`, `embedding_unavailable`,
`embedding_timeout`, `embedding_dimension_mismatch`, `llm_disabled`, `llm_unavailable`,
`llm_timeout`, `llm_invalid_response`, `llm_ungrounded_response`,
`no_evidence_for_generation`, `evidence_context_truncated`. All responses also
carry factual caveats; per-hit warnings identify missing source attributes.
New warning codes may appear, so render an unknown code safely.

## Display and privacy

Render OSM names/addresses as escaped plain text; they are untrusted source data,
not markup or instructions. Preserve `null` as unknown. Do not display a missing
name as a real business name. Display “© OpenStreetMap contributors” linked to
the supplied copyright URL and preserve `ODbL-1.0` metadata when redistributing.
Show `osm_source_only` status and retrieval timestamp where freshness matters.

Do not turn a preference query into a verified badge (Wi-Fi, quiet, cozy, indoor).
Do not display “open now,” walking distance/time or a reachable-from-user claim
from retrieval/RAG alone. Use the route endpoint below for ORS graph metrics from
a public anchor. Treat center
coordinates as representative points rather than building entrances.
Avoid putting exact user locations or raw queries in analytics, URL/access logs,
or error reporting. Backend validation errors omit submitted inputs and provider
diagnostics; the API intentionally echoes the original query only in successful
retrieval/RAG responses. CORS is not authentication.

## Walking route planner

Send the natural-language preference query with one of `mega_silk_way`,
`botanical_garden`, `expo_nur_alem`, `nurzhol_boulevard`. The backend loads
coordinates exclusively from `shared/anchors.json`. Do not send latitude,
longitude, a key, `top_k` or other additional fields.

```js
async function planWalk(apiBase, query, startAnchorId = 'expo_nur_alem') {
  const response = await fetch(`${apiBase}/api/v1/routes/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      start_anchor_id: startAnchorId,
      duration_minutes: 60,
      query,
      round_trip: true,
      language: 'ru', // 'kk' and 'en' are also supported
    }),
  });
  if (response.status === 422) throw new Error('Check the route form fields');
  if (response.status === 413) throw new Error('Route request is too large');
  if (!response.ok) throw new Error(`Route service failed: ${response.status}`);
  return response.json();
}

const plan = await planWalk(apiBase, 'Хочу спокойную прогулку возле EXPO');
// Clear the previous route and stops before displaying this result.
routeLayer.clearLayers();
stopLayer.clearLayers();
recommendationElement.textContent = plan.recommendation;
warningsElement.textContent = plan.warnings.join('\n'); // Or localize known codes.

if (plan.status === 'no_route') {
  // Show the localized recommendation and reason; do not draw a substitute line.
  reasonElement.textContent = plan.reason;
} else {
  reasonElement.textContent = '';
  // Leaflet consumes GeoJSON [longitude, latitude] directly.
  L.geoJSON(plan.route_geojson).addTo(routeLayer);
  for (const stop of plan.stops) {
    const label = document.createElement('span');
    label.textContent = `${stop.order}. ${stop.name ?? 'Название неизвестно'}`;
    // Leaflet markers use [latitude, longitude].
    L.marker([stop.latitude, stop.longitude]).bindTooltip(label).addTo(stopLayer);
  }
  timeElement.textContent = `${plan.estimated_total_minutes.toFixed(1)} мин ` +
    `(пешком ${plan.walking_minutes.toFixed(1)}, посещения ${plan.visiting_minutes})`;
  distanceElement.textContent = `${(plan.total_distance_meters / 1000).toFixed(2)} км`;
}
// Show OSM/ODbL attribution and routing provenance for BOTH outcomes.
attributionElement.textContent = `${plan.dataset.attribution} (${plan.dataset.license})`;
const routing = plan.routing_provenance.directions ?? plan.routing_provenance.matrix;
provenanceElement.textContent = routing
  ? `${routing.provider} / ${routing.profile} / ${routing.mode} / ${routing.retrieved_at}`
  : 'Маршрут ORS не получен';
```

The example assumes Leaflet `L`, initialized `routeLayer`/`stopLayer` groups and
the named DOM elements. Clear stale time/distance labels along with map layers
before rendering a new result. In MapLibre, pass `route_geojson` to a GeoJSON
source and render a line layer. Never rebuild the route by connecting the POIs.
The route can start/end at nearby snapped graph points rather than the exact
representative OSM coordinates. `round_trip=true` includes the start again at
the end of the Directions waypoints; it is not an extra POI stop. For `false`,
the route ends at the last stop.

| Response field | Meaning |
| --- | --- |
| `status` | Discriminator: `success` or `no_route`; both return HTTP 200 |
| `start_anchor_id`, `start_anchor` | Catalog ID and source-backed coordinate/limitations |
| `requested_duration_minutes`, `round_trip`, `language` | Validated input values |
| `estimated_total_minutes` | Directions walking time plus planned visit allowances |
| `walking_minutes`, `total_distance_meters` | Actual validated ORS Directions summary |
| `visiting_minutes` | Sum of per-stop planned allowances, not measured time |
| `stops` | 1–3 public POIs, plus `order`, `visiting_minutes`, `visit_duration_source`, `selection_source`, `explanation` |
| `route_geojson` | Validated ORS FeatureCollection with LineString; use it directly |
| `recommendation` | Deterministic localized text about the selected stops/limitations |
| `retrieval_mode` | `lexical` or `hybrid`, including lexical fallback if embedding fails |
| `routing_provenance.matrix`, `.directions` | Provider/profile/mode, retrieval timestamp, endpoint and original metadata; individually nullable |
| `dataset` | Original OSM attribution/license, hashes and capture timestamps |
| `warnings` | Limitations and fallback codes; display safely, including unknown codes |

`no_route` adds `reason`; its `stops=[]`, `route_geojson=null` and all four
time/distance metrics are `null`. Do not render zero-minute/zero-meter success.
Reasons are `no_candidates`, `unreachable`, `budget_exceeded`, `ors_unconfigured`,
`ors_timeout`, `ors_unavailable`, `ors_invalid_response`. `ors_unconfigured` needs
server configuration; unavailable/timeout responses can offer a manual retry.
GeoAdapter normalizes live transport timeouts into `ors_unavailable` with
`ors_transport_error`. Provenance records only responses actually received; a
failed Directions call can leave Matrix provenance available. A budget failure
can preserve Directions provenance without returning unusable geometry.

Input duration is an integer 30–180, query nonblank and ≤1000 characters,
round trip is a boolean (default true), language `ru|kk|en` (default ru).
No automatic request loop is recommended: each plan may make one Matrix and
two Directions calls, with up to three provider HTTP attempts per call.

Show `nearby_fallback_not_query_match` prominently: these real places were
chosen by proximity because local retrieval was sparse; their suitability for
the query is not established. Each stop identifies `retrieval` or
`nearby_fallback`. `bounding_box_center_not_verified_entrance:<id>` applies to
the anchor or a selected POI: the point is not an evidenced entrance. Show
`start_anchor.limitations` as plain text. Preserve `null` source attributes.
`visit_times_are_planned_estimates`, `preferences_not_verified`,
`current_opening_status_unknown`, `entrance_and_accessibility_not_verified`
describe factual limits even after successful routing. ORS may report its own
warnings in `route_geojson.features[0].properties.warnings`; the top-level
`ors_directions_warning` signals their presence. OSM/provider text is untrusted.

The planner does not call Qwen or reselect stops through RAG. The greedy route
is bounded, conservative and not guaranteed optimal. Weather is a separate service
documented below; the planner does not consume it yet. H3 remains separate work.

## Weather

```js
async function loadWeather(apiBase, startAnchorId = 'expo_nur_alem') {
  const params = new URLSearchParams({ start_anchor_id: startAnchorId });
  const response = await fetch(`${apiBase}/api/v1/weather?${params}`);
  if (response.status === 422) throw new Error('Выберите зону из каталога');
  if (!response.ok) throw new Error(`Weather service failed: ${response.status}`);
  return response.json();
}

const weather = await loadWeather(apiBase);
weatherElement.textContent = weather.status === 'unknown'
  ? 'Погодные данные недоступны'
  : `Температура: ${weather.temperature_c == null ? 'неизвестна' : `${weather.temperature_c} °C`}; ` +
    `ветер: ${weather.wind_speed_kmh == null ? 'неизвестен' : `${weather.wind_speed_kmh} км/ч`}`;
probabilityElement.textContent = weather.precipitation_probability_percent == null
  ? 'Вероятность осадков неизвестна'
  : `Вероятность осадков: ${weather.precipitation_probability_percent}% ` +
    `(за час до ${weather.forecast_valid_at})`;
weatherTimeElement.textContent =
  `Текущая модель: ${weather.observed_at ?? 'нет данных'}; получено: ${weather.fetched_at}`;
weatherWarningsElement.textContent = weather.warnings.join('\n'); // Localize known codes.
weatherAttributionElement.textContent = 'Weather data by Open-Meteo (open-meteo.com)';
```

The named DOM elements belong to the frontend. Use `textContent`, clear old values
when loading/failing, and display a link to https://open-meteo.com/ for attribution.
Do not send GPS, forecast parameters, or credentials. The same four catalog anchor
IDs used by route planning are supported; extra query parameters return 422.

| Response field | Meaning |
| --- | --- |
| `status` | `available` means at least one usable indicator; `unknown` means none |
| `anchor_id` | Requested catalog zone |
| `temperature_c`, `apparent_temperature_c` | Current model °C; individually nullable |
| `precipitation_mm` | Current model-step amount in mm (typically 15 min); nullable |
| `precipitation_probability_percent` | 0–100%, probability for the hour ending at `forecast_valid_at`; nullable |
| `wind_speed_kmh`, `weather_code` | Current km/h and WMO code; nullable |
| `observed_at` | Timestamp for available current model indicators, never borrowed from hourly forecast |
| `forecast_valid_at` | End of probability's preceding-hour interval, selected to contain retrieval time |
| `timezone` | Always `Asia/Almaty`; timestamps include its UTC offset |
| `fetched_at`, `source` | Fetch completion/attempt time and `open-meteo`; preserved on cache hits |
| `cache_status` | `miss` for live fetch attempts, `hit` for cached responses |
| `warnings` | Machine codes for model limitations, missing data, failures and walking heuristics |

`unknown` is an intentional HTTP 200 fallback with all weather indicators,
`observed_at` and `forecast_valid_at` null; show unavailable, never zero or good
weather. Partial `available` responses can also contain null current conditions
or null probability, and the UI must handle each independently. `observed_at` is
an Open-Meteo model estimate, not a measured weather-station reading.
At 21:05, probability ending at 22:00 describes the 21:00–22:00 hour, while
temperature can have its own 21:00 or 21:05 model timestamp. At an exact hour,
the next interval is selected. Do not label hourly probability as observed rain.

| Warning | Meaning / UI handling |
| --- | --- |
| `weather_model_estimate_not_station_observation` | Model output, not a station measurement |
| `weather_current_incomplete` | One or more current indicators missing; preserve nulls |
| `weather_hourly_probability_unavailable` | No usable probability for the interval containing fetch time |
| `weather_conditions_unknown` | No trustworthy weather indicators; show unavailable |
| `weather_timeout`, `weather_connection_error` | Provider timeout or connection/DNS/protocol failure |
| `weather_rate_limited` | Provider HTTP 429; avoid automatic rapid retries |
| `weather_upstream_unavailable` | Provider HTTP 5xx |
| `weather_http_error` | Other non-success provider status |
| `weather_invalid_json`, `weather_invalid_response` | Invalid JSON or failed units/value/time/schema validation |
| `weather_strong_wind` | Wind ≥35 km/h by default |
| `weather_significant_precipitation` | Current-step precipitation ≥2 mm by default |
| `weather_low_temperature` | Feels-like ≤0 °C; falls back to air temperature only when feels-like is absent |
| `weather_high_precipitation_probability` | Selected hourly probability ≥70% by default |

Show unknown future warning codes safely as text. The four walking thresholds are
server-configured product heuristics, not official danger criteria. Missing data
and absence of heuristic warnings cannot establish safe or pleasant weather.
Weather warnings do not modify ORS walking times, geometry or route budgets.

Cache TTL is 10 minutes with at most four entries per process; the forecast hour
boundary or a now-stale current observation can force earlier refresh. Hits retain
original evidence/fetch times. Failed refreshes discard old evidence and return
unknown, cached for 30 seconds. Multiple workers have separate caches. No polling
loop is needed for the MVP; load on anchor selection and allow manual retry.

For backend integration, use the injected service directly:

```python
from app.schemas.weather import WeatherResponse
from app.services.weather_service import WeatherService

def weather_for_plan(service: WeatherService) -> WeatherResponse:
    return service.get_weather("expo_nur_alem")
```

`get_weather_service` resolves the shared application instance in FastAPI;
`create_app(weather_service=...)` accepts a replacement instance for tests.
Calling this synchronous service from an async route requires a worker thread.
The current Route Planner is intentionally not wired to it. No RAG or ORS
dependency is introduced into WeatherService. See
[weather.schema.json](../contracts/weather.schema.json), `/openapi.json`,
[the configuration table](../apps/api/README.md#open-meteo-weather) and
[the official Open-Meteo definitions](https://open-meteo.com/en/docs).
