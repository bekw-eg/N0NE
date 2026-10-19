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
is bounded, conservative and not guaranteed optimal. Weather and H3 remain
separate Developer №1 tasks.
