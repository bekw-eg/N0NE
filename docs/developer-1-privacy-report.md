# H3 Privacy Integration — Developer №1

Implemented on `feature/geo-h3-privacy`, based on `origin/main` at `d025496`.
PR #9 (Weather) was confirmed merged before branching. The working tree was
clean; existing Git author/email were retained. No frontend files, anchor
coordinates, ORS routing contracts or Weather contracts were changed.

## Behavior

`POST /api/v1/privacy/resolve-h3` accepts only a JSON body containing `h3_cell`.
The dependency is official `h3-py` (`h3>=4,<5`, locked to **4.5.0**). Validation
uses `is_valid_cell()` and `get_resolution()`; only strict 15-character
hexadecimal cell IDs at resolution **8** pass. Non-cells, resolutions 7/9,
overlong/wrong-type input, missing fields and extra properties are rejected.
This includes `latitude`, `longitude`, `gps`, `coordinates` and any other field.
All query parameters are rejected. The existing body limiter caps input at 16 KiB.
The backend provides no GPS-to-H3 conversion endpoint.

The stateless service derives only the cell center via `cell_to_latlng()`.
Coverage uses the existing POI snapshot bounds: latitude 51.075–51.145,
longitude 71.385–71.455, inclusive by cell center. This is the supported MVP
rectangle, not the administrative boundary of Astana. A valid foreign cell or
border cell whose center falls outside returns HTTP 200 `no_nearby_anchor`,
with `reason=outside_supported_area`. This is an explicit unsupported-area
result, distinct from invalid H3 syntax/resolution (422).

All four supported anchors are loaded from `shared/anchors.json`:
`expo_nur_alem`, `mega_silk_way`, `botanical_garden`, `nurzhol_boulevard`.
Haversine selects the nearest approximate anchor, with anchor ID as a stable
tie breaker. `PRIVACY_MAX_ANCHOR_DISTANCE_M` defaults to **3000**; configuration
accepts finite values >0–10000 m. The unrounded distance must meet the limit.
Otherwise the result is `no_nearby_anchor`, `reason=no_anchor_within_radius`.
No-match responses contain neither a `start_anchor_id` nor a distance.

Matched responses return the existing `start_anchor_id`, resolution 8 and a
rounded integer estimate in straight-line meters from cell center to catalog
anchor. They never claim walking time/distance or distance from exact user GPS.
The existing Route Planner receives only this anchor ID and still sends catalog
coordinates to ORS. No H3 center or invented GPS waypoint enters a route.
EXPO's bounding-box center remains a representative point, not a confirmed
entrance. A mapped entrance still does not establish opening/accessibility.

Warnings are typed machine codes:

| Result | Codes |
| --- | --- |
| `matched` | `approximate_location`, `anchor_distance_not_walking_distance` |
| `no_nearby_anchor` | `approximate_location`, `manual_anchor_selection_required` |

## Reproducible public-catalog example

The public EXPO point in the committed catalog generates resolution-8 cell
`882153806dfffff` (not a user's geolocation):

```json
{
  "status": "matched",
  "start_anchor_id": "expo_nur_alem",
  "resolution": 8,
  "distance_estimate_m": 394,
  "warnings": ["approximate_location", "anchor_distance_not_walking_distance"]
}
```

The public catalog points for Mega Silk Way, Botanical Garden and Nurzhol also
resolve to their expected anchors. The API does not return the submitted H3 ID,
GPS, or the center coordinates in either outcome.

## Validation

All tests below ran offline on Python 3.11; no real user location was accessed.
Anchor tests generate cells from the public catalog. An existing public POI
tests conservative border behavior; the Eiffel Tower's public landmark point
tests non-Astana handling. Network access is blocked/mocked by the suites.

| Check | Result |
| --- | --- |
| `uv sync --python 3.11` in `apps/api` | Pass; 34 packages |
| `uv run pytest -q` in `apps/api` | **315 passed**, 2 dependency deprecation warnings |
| `uv run ruff check .` | Pass |
| `uv run ruff format --check .` | Pass; 51 Python files formatted |
| `uv run mypy app scripts` | Pass; 42 source files |
| Geo suite (`packages/geo/tests`) | **101 passed** |
| Data suite (`packages/data_pipeline/tests`) | **39 passed** |
| Integration suite (`tests/integration`) | **36 passed** |
| `git diff --check` | Pass |

Total: **491 tests passed**, including **50 new privacy cases and 4 new
H3 → Route Planner handoff cases**. Coverage includes malformed IDs, string/body
limits, resolution rejection, edges/vertices, unsupported areas, no close anchor,
all four zones, deterministic ties, pre-rounding distance limits, forbidden GPS
fields, response/log redaction, warning codes, OpenAPI and schema drift.
Four end-to-end API handoff tests check that Matrix/Directions retain catalog
start coordinates rather than H3 centers. Existing Route Planner, Weather, POI,
retrieval and RAG regressions all pass.

The current Windows checkout has a Cyrillic directory in its path. Python 3.11
did not resolve editable-package `.pth` paths correctly when tests were launched
directly, so the checks used explicit import paths in the shell (no repository
behavior changes or alternate dependencies):

```powershell
# From apps/api:
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = "$((Get-Location).Path);$((Resolve-Path '../../packages/geo/src').Path);$((Resolve-Path '../../packages/data_pipeline/src').Path)"
uv sync --python 3.11
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts

# From the repository root, for the three separate existing suites:
$env:PYTHONPATH = "$((Resolve-Path '.').Path);$((Resolve-Path 'apps/api').Path);$((Resolve-Path 'packages/geo/src').Path);$((Resolve-Path 'packages/data_pipeline/src').Path)"
& 'apps/api/.venv/Scripts/python.exe' -m pytest -q packages/geo/tests
& 'apps/api/.venv/Scripts/python.exe' -m pytest -q packages/data_pipeline/tests
& 'apps/api/.venv/Scripts/python.exe' -m pytest -q tests/integration
```

`h3-py` currently lacks type stubs/`py.typed`; the mypy missing-import override
is restricted to `h3`/`h3.*`. Project code remains under strict mypy checking.

## Frontend handoff and privacy limitations

[Developer №3 integration guide](developer-3-api-integration.md#approximate-location-with-h3)
contains the browser permission flow, `h3-js` 4.x `latLngToCell(lat, lng, 8)`,
cell-only POST, existing route call, permission-denied/unavailable fallback and
a manual four-zone selector. The
[JSON schema](../contracts/privacy.schema.json) contains the response union and
`$defs.H3ResolveRequest`; runtime OpenAPI exposes both. Actual frontend wiring
remains Developer №3's work, as requested.

Exact GPS stays in the browser callback and is not sent to the API. Neither GPS
nor H3 should enter localStorage, cookies, URLs, logs, analytics or exception
capture. The service retains no cell/center history, cache, database or Redis
state; it calls no external location API and forwards no H3 data to ORS, Weather
or RAG. Request data necessarily exists transiently in process memory. Request
models suppress cell values in repr/validation-error strings. API validation
errors omit submitted values; service code emits no request/body logs. Matched
and unmatched responses carry `Cache-Control: no-store`.

**H3 is not anonymity.** A resolution-8 cell discloses an approximate area whose
center/boundary can be recovered. Repeated cells, timestamps, IP addresses or
account data can enable linkage and movement inference. HTTPS is required in
deployment, and browser permission does not substitute for data minimization.
Disable/redact request-body capture, exception-local capture and session replay
in hosting/proxy/APM systems. Rejected GPS or cells in an arbitrary URL may reach
infrastructure access logs before rejection, so query strings require redaction
there. The application cannot prevent a modified client from transmitting extra
data to unrelated services. Catalog anchor coordinates returned by the existing
Route Planner are public data and do not represent the user's precise position.

## Known limitations

- Support covers the current snapshot rectangle and four starting zones. It
  does not cover all Astana, and cell-center checks can exclude border points.
- Straight-line proximity does not establish walkability, entrance location,
  current access, or time to reach the start. ORS routing begins at the anchor.
- Deployment logging/APM controls and Developer №3's UI integration must follow
  the handoff; this backend PR cannot configure external infrastructure.
- The existing TestClient stack emits deprecation warnings for httpx and anyio's
  BlockingPortal alias. They do not fail tests; unrelated dependency migration
  was left outside this task.
- The Windows editable-import workaround above is needed in this local checkout.

## Changed files

- `apps/api/app/schemas/privacy.py` — strict request and discriminated responses.
- `apps/api/app/services/privacy_service.py` — coverage and nearest-anchor matching.
- `apps/api/app/routers/privacy.py` — POST endpoint and query rejection.
- `apps/api/app/main.py` — service lifecycle and router registration.
- `apps/api/app/core/config.py` — finite configurable matching radius.
- `apps/api/.env.example` — matching-radius environment example.
- `apps/api/pyproject.toml`, `apps/api/uv.lock` — official H3 4.x dependency/typing override.
- `apps/api/tests/test_privacy.py` — offline privacy/API/contract tests.
- `apps/api/tests/test_routes.py` — H3-to-planner integration for all four anchors.
- `contracts/privacy.schema.json` — generated public request/response contract.
- `apps/api/README.md` — endpoint, configuration and privacy notes.
- `docs/developer-3-api-integration.md` — browser and manual-selection handoff.
- `docs/developer-1-privacy-report.md` — this implementation/validation report.

PR target: `main`. Merge requires the user's authorization and is not part of
this task. Commit and PR identifiers are supplied in the delivery message.
