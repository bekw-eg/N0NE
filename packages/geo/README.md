# VibeRoute ORS walking adapter (developer 1)

Standalone Python 3.11+ integration for OpenRouteService's `foot-walking` profile.
It is independent of the pending POI collector PR. It does not define HTTP
recommendation endpoints or change the shared backend contracts.

Install and check from the repository root:

```powershell
uv sync --project packages/geo --group dev
uv run --project packages/geo python -m pytest packages/geo/tests tests/integration/test_geo.py -q
uv run --project packages/geo ruff check --config packages/geo/pyproject.toml packages/geo apps/api/app/integrations/geo_adapter.py scripts/geo_smoke.py tests/integration/test_geo.py
uv run --project packages/geo mypy --config-file packages/geo/pyproject.toml packages/geo/src apps/api/app/integrations/geo_adapter.py
```

## Use from the backend

Install this package into the API environment (`pip install -e packages/geo`). The
backend facade is `apps/api/app/integrations/geo_adapter.py`; it exports the same
public types as `viberoute_geo`:

```python
from viberoute_geo import (
    DirectionsRequest,
    GeoAdapter,
    GeoPoint,
    IsochronesRequest,
    MatrixRequest,
)

# Public landmarks or an origin already reduced to an H3 cell center upstream.
# Do not feed the adapter raw user GPS coordinates.
points = [
    GeoPoint(longitude=71.4073303, latitude=51.0890897),
    GeoPoint(longitude=71.4165705, latitude=51.1061652),
]
geo = GeoAdapter.from_env()
route = geo.directions(DirectionsRequest(locations=points))
areas = geo.isochrones(IsochronesRequest(origin=points[0]))
matrix = geo.matrix(MatrixRequest(locations=points))
print(route.duration_seconds, route.distance_meters)
```

Set `ORS_API_KEY` in the process environment. The optional `ORS_BASE_URL` defaults
to `https://api.heigit.org/openrouteservice`. Directions, isochrones, and matrix
paths append `/v2/...` to that base; do not add another `/openrouteservice` segment.
Explicit overrides remain supported, including a trailing slash. Update any old
`ORS_BASE_URL` in your deployment or local `.env`, or remove it to use the new default.
A local `.env` can be loaded explicitly with
`uv run --env-file .env ...`; the adapter does not load files implicitly. The real
key belongs in the ignored `.env`; `.env.example` contains only empty configuration.
Keys travel in the Authorization header. URLs require HTTPS without credentials,
queries, or fragments; redirects are rejected. Provider messages and transport
exception contents are excluded from public errors; recordings redact secret keys
and the configured credential value.

The methods are synchronous. Use them from sync FastAPI handlers or a worker
thread when integrating with an async orchestrator. Injected `httpx.Client`
instances are owned and closed by the caller; otherwise each call owns its client.

## Return values and failure behavior

- Directions return typed GeoJSON LineString geometry and summary distance in
  **meters** / duration in **seconds**. These are provider estimates on the walking
  graph, not elapsed time measured during a real walk.
- Isochrones return validated Polygon/MultiPolygon features. Defaults are 600 and
  900 seconds; requests allow one or two unique, increasing ranges up to 900 seconds.
- Matrices preserve the requested source/destination order and can be rectangular.
  Durations are seconds; distances are meters. Null pairs stay unreachable; matrix
  symmetry is never assumed. Returned snapping locations/distances are retained.
- Invalid geometry, ring closure, waypoint indices, metrics, dimensions, or range
  mismatches raise `GeoError(code="invalid_response", ...)`. GeoError also exposes
  sanitized HTTP status and numeric provider error code when available.
- Missing credentials, unavailable routes, rate limits, and provider failures are
  explicit errors. No straight-line geometry, speed estimate, or successful empty
  result is fabricated. Retries are capped at three requests, with at most 30 seconds
  per backoff for 429/502/503/504 or transport failures.
- Client caps are 25 route locations and 50 matrix locations; these are local
  guardrails, not a promise about provider account quotas.

Every result includes provider, profile, original retrieval time, endpoint, full
provider metadata (including attribution/graph dates), and `mode=live|recorded`.
Render provider attribution alongside the map. GeoJSON uses **longitude, latitude**.

The two initial public anchors come from real OSM objects recorded by the POI
collector: Mega Silk Way and the Botanical Garden. Both points are bounding-box
centers, **not verified entrances**. Directions use an explicit 100-meter default
snapping radius (configurable up to 1,000 meters). Returned paths connect snapped
graph positions; the summary does not establish a walkable connection from a
building interior, an accessible entrance, opening status, or covered passage.
Matrix snapping distances are offsets, not additional walking legs. The other
two project areas can be added after their anchor/entrance evidence is collected.

## Live capture and explicit offline replay

The smoke CLI accepts public anchor IDs, not a user GPS pair. With a configured key:

```powershell
uv run --project packages/geo --env-file .env python scripts/geo_smoke.py --recordings-dir data/tmp/geo-live/recordings --output-dir data/tmp/geo-live/demo
```

For an offline demo using the checked-in real ORS responses:

```powershell
uv run --project packages/geo python scripts/geo_smoke.py --mode recorded --recordings-dir data/geo/recordings --output-dir data/tmp/geo-replayed
```

The recording filename identifies the operation, walking profile, and exact JSON
request. The capture also stores endpoint, retrieval time, response SHA-256, and
the sanitized provider response. Only successfully validated responses are saved.
Offline mode validates the request, endpoint, hash, age, and response structure
again. A modified origin, destination, radius, or matrix selection cannot reuse an
unrelated response. No live failure silently switches into recorded mode.

The three checked-in captures from PR #2 were retrieved from
`https://api.openrouteservice.org` before this migration. Their original bytes,
response hashes, timestamps, endpoints, and demo provenance are retained. With
the new default base URL, recorded mode accepts only these three unchanged legacy
captures, pinned by the SHA-256 of each complete file in the adapter. Exact request,
profile, response-hash, age, and geometry checks still apply. Replays keep the
legacy endpoint and original retrieval time and are always labeled `recorded`.
Changing any capture bytes invalidates this compatibility, even if the response
hash is recomputed. Arbitrary legacy recordings and custom base URLs still require
an exact endpoint match. This exception never makes an HTTP request and never
falls back to the old service. Capture new live responses in a separate directory,
as above, to preserve these historical fixtures.

The default maximum recording age is 24 hours; future timestamps beyond five
minutes are rejected. For a deliberate historical demo, pass
`--max-recording-age-seconds` explicitly and keep the `recorded` label and original
timestamp visible. A response hash checks consistency, not authenticity against
malicious replacement of an entire recording.

Library recording is opt-in via `recordings_dir=Path(...)`; ordinary backend calls
do not persist coordinates. The CLI records only selected public anchors. The
adapter itself is an internal provider boundary; frontend H3 conversion and backend
origin validation remain necessary integration work.

The demo contains real provider output. Unit tests use clearly labeled synthetic
responses only in memory/temporary directories. Integration tests replay actual
checked-in responses with a fixed capture-time clock and forbid network access.

Provider references:

- [Official HeiGIT endpoint migration](https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912)
- [Directions request and return types](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/requests-and-return-types)
- [Isochrones](https://giscience.github.io/openrouteservice/api-reference/endpoints/isochrones/)
- [Matrix units, indexing, and metrics](https://giscience.github.io/openrouteservice/api-reference/endpoints/matrix/)
