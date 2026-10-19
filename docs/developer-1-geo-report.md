# VIBEROUTE — DEVELOPMENT REPORT

Developer Role: **1 — Data & Geo Engineer**.

GitHub Login: `bekw-eg`.

Git Author Name: `bekw-eg`, from the existing Git configuration.

Git Author Email: configured, withheld. GitHub associates both the author and
committer of the implementation commit with `bekw-eg`; no identity overrides
were used.

Branch: `feature/data-geo-routing`, based on `main`. This task is independent of
collector PR #1, which remains a separate review.

Implemented:

- Actual ORS `foot-walking` directions, GeoJSON, 10/15-minute isochrones, and
  time/distance matrices with explicit units and provider provenance.
- Typed input/output validation, coordinate/range constraints, route waypoints,
  polygon ring closure, matrix dimensions, and null/unreachable pairs.
- Bounded retries, controlled errors, header credentials, and secret redaction.
- Opt-in recording and explicit offline replay with request/endpoint/hash/age
  checks; unavailable paths do not become straight-line walking estimates.
- Two real OSM public anchors, a CLI, actual provider captures, and demo exports.
- A backend import facade with no FastAPI/RAG/recommendation contract changes.

Files Changed:

- `.env.example`, `.gitattributes`, `README.md`.
- `packages/geo/`: package metadata, lockfile, typed models, adapter, CLI,
  documentation, and unit tests.
- `apps/api/app/integrations/geo_adapter.py`.
- `shared/anchors.json`, `scripts/geo_smoke.py`.
- `data/geo/`: three actual ORS captures, normalized demo outputs, and source notes.
- `tests/integration/test_geo.py`.
- This delivery report.

Tests Executed:

```powershell
uv sync --project packages/geo --group dev
uv run --project packages/geo python -m pytest packages/geo/tests tests/integration/test_geo.py -q
uv run --project packages/geo ruff check --config packages/geo/pyproject.toml packages/geo apps/api/app/integrations/geo_adapter.py scripts/geo_smoke.py tests/integration/test_geo.py
uv run --project packages/geo ruff format --check --config packages/geo/pyproject.toml packages/geo apps/api/app/integrations/geo_adapter.py scripts/geo_smoke.py tests/integration/test_geo.py
uv run --project packages/geo mypy --config-file packages/geo/pyproject.toml packages/geo/src apps/api/app/integrations/geo_adapter.py
uv run --project packages/geo --env-file .env python scripts/geo_smoke.py --recordings-dir data/geo/recordings --output-dir data/geo/demo
uv run --project packages/geo python scripts/geo_smoke.py --mode recorded --recordings-dir data/geo/recordings --output-dir data/tmp/geo-replayed
git diff --cached --check
```

Tests Result:

- **52 passed**: 49 unit cases and 3 integration cases using actual provider captures.
- Ruff lint and formatting checks passed; strict mypy passed for all 5 source files.
- All three actual ORS requests completed successfully on 19 October 2026,
  19:54:40–19:54:41 Asia/Qyzylorda (14:54 UTC).
- Mega Silk Way → Botanical Garden: **2,272.7 m**, **1,636.3 s**, 91 geometry positions.
- Actual 600/900-second isochrones and 2×2 walking matrix were saved and replayed.
- Offline tests forbid HTTP clients, compare exported geometry to real snapshots,
  and verify that a missing key fails before opening a network client.
- A replay mismatch between integer/float defaults for snapping radius was found
  by integration testing and fixed before publication.
- Staged-file scan checked all 25 implementation files: **no credential matches**.
  The user-provided ORS key is stored only in the ignored local `.env`.
- Execution was tested on CPython **3.14.0**; 3.11+ is declared but 3.11 itself
  was not exercised.

Commit SHA (implementation): `9dcbb86f2e08579219d9734aadf92c23b70cd21a`.

Push Status: **successful**, feature branch published.

Pull Request URL: https://github.com/bekw-eg/N0NE/pull/2 (open, ready for review).

This report is delivered in a separate documentation commit on the same PR; the
implementation SHA above identifies the tested package, fixtures, and integration.

Integration Notes:

- Install `packages/geo` into the API environment. The public facade exports
  `GeoAdapter`, request/result types, and controlled `GeoError` failures.
- The client is synchronous; use sync handlers or a worker thread in an async API.
- Units: seconds and meters. GeoJSON positions: longitude, latitude.
- Preserve `live`/`recorded` labels, original timestamps, provider graph metadata,
  attribution, and null reachability when rendering or planning routes.
- H3 reduction and backend origin validation are required before private user
  locations reach this internal adapter; no GPS-intake endpoint was added.

Known Limitations:

- Both anchors are OSM bounding-box centers, not verified entrances. Matrix snap
  offsets are 83.39 m and 8.26 m; no walkable interior-to-graph connection is proven.
- Provider graph date is 2026-09-20, OSM date is 2026-09-13. These estimates do not
  establish current access, closures, weather, or covered passage.
- Recordings have a 24-hour default age limit. Explicit historical demos may
  override the age limit while retaining recorded mode and the source timestamp.
- The initial catalog covers two landmarks; EXPO/boulevard entrance evidence is
  still needed. No shared API schema has been agreed or changed here.
- PR #2 remains open for owner review. No merge or new direct commit to `main`
  was performed.

Next Recommended Task:

- Owner review of PRs #1 and #2; merge decisions remain with the owner.
- Add Open-Meteo integration and explicit live/simulated weather policy, then H3
  privacy helpers and the remaining source-backed public anchors.
