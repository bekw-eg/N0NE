# Real ORS walking snapshot

This directory's `recordings/` and `demo/` are the immutable PR #2 snapshot.
The current four-zone HeiGIT scenario is stored separately in
[`anchors/`](anchors/README.md).

These are actual HTTPS responses from OpenRouteService for **public landmarks**.
They are not synthetic route fixtures or user GPS histories.

Captured on **19 October 2026, 19:54:40–19:54:41 Asia/Qyzylorda** (14:54 UTC), using
the `foot-walking` directions, isochrones, and matrix endpoints:

- Origin: Mega Silk Way, OSM way 499328514.
- Destination: Botanical Garden, OSM way 1196402246.
- Route: **2,272.7 meters**, **1,636.3 seconds** (about 27.3 minutes), 91 positions.
- Isochrones: **600 / 900 seconds** from the origin.
- Matrix: 2 × 2, meters/seconds, including source/destination snapping information.
- Provider graph date: **2026-09-20**; underlying OSM date: **2026-09-13**.

The public anchor coordinates are OSM bounding-box centers, not verified entrances.
The matrix reports snap offsets of 83.39 m and 8.26 m. They do not establish
walkable connections from an interior point to the graph. The route summary is a
provider estimate for the graph path; it does not prove opening status, current
closures, accessibility, or a continuously covered route.

`recordings/` contains the exact request, endpoint, retrieval time, sanitized
provider response, and response hash for each operation. `demo/` contains normalized
GeoJSON, matrix JSON, and the source-backed public anchors. GeoJSON has a
`viberoute_provenance` member with `mode=live` and the original source metadata.

These historical captures and demo exports retain their original
`https://api.openrouteservice.org/v2/...` endpoints. They are not evidence of live
requests to the new `https://api.heigit.org/openrouteservice` API. The adapter pins
the SHA-256 of each complete capture file to permit these three unchanged fixtures
in recorded mode with the new default. Request, profile, response-hash, age, and
geometry checks still apply; replays preserve the original endpoint and timestamp.
Keep these files unchanged, including their LF line endings. New live captures
should use a separate directory, such as `data/tmp/geo-live/recordings`.

For an explicit offline replay and response validation, from the repository root:

```powershell
uv run --project packages/geo python -c 'import json; from pathlib import Path; d=json.loads(Path("data/geo/demo/anchors.json").read_bytes()); p=Path("data/tmp/legacy-anchors.json"); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"schema_version":"0.1.0","description":"Historical PR 2 centers","anchors":[d["origin"],d["destination"]]}), encoding="utf-8")'
uv run --project packages/geo python scripts/geo_smoke.py --mode recorded --anchors data/tmp/legacy-anchors.json --recordings-dir data/geo/recordings --output-dir data/tmp/geo-replayed
```

Replayed outputs are labeled `recorded`. The default maximum snapshot age is
24 hours; a historical demo needs an explicit `--max-recording-age-seconds` value.
Runtime timestamps/age remain visible. Integration tests use the capture time as
their clock so the snapshot can be tested reproducibly without network access.

Provider attribution retained in the response metadata:
**openrouteservice.org | OpenStreetMap contributors**. Keep the provider attribution
visible in downstream maps; see the [ORS terms](https://openrouteservice.org/terms-of-service/)
and [OpenStreetMap copyright](https://www.openstreetmap.org/copyright).
