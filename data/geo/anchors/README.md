# Four-zone OSM and HeiGIT snapshot

Actual public-source data captured on 19 October 2026. This snapshot is separate
from the historical PR #2 captures in the parent directory.

- `sources/`: four official OSM API responses with source URLs, retrieval times,
  full object metadata, node membership, tags and OSM attribution. No invented
  entrance nodes. The requested Overpass service returned HTTP 406 and its Kumi
  mirror timed out; official `api.openstreetmap.org` responses succeeded.
- `recordings/`: 19 real successful HeiGIT responses, exact requests, endpoints,
  retrieval timestamps and response SHA-256 hashes. Capture window:
  **16:17:27–16:17:33 UTC / 21:17:27–21:17:33 Asia/Qyzylorda**.
- `demo/`: 14 route GeoJSON files, four two-feature isochrone GeoJSON files,
  one 4×4 matrix, the anchor catalog and an authoritative `manifest.json`.
  These original exports carry `mode=live`. Replays carry `mode=recorded`.

All 12 directed zone routes succeeded, as did E↔F at Mega Silk Way, 10/15-minute
isochrones for all four zones, and the matrix. GeoJSON positions are **longitude,
latitude**. Every geometry passes the adapter's validation; an additional Shapely
check found all 22 geometries valid and nonempty. Shapely was used only as an
external QA tool and was not added to the project's dependencies.

Run from the repository root:

```powershell
uv run --project packages/geo python scripts/geo_smoke.py --all-anchors --mode recorded --output-dir data/tmp/anchors-replayed
```

No key or HTTP connection is needed for replay. Request, endpoint, profile,
response hash, geometry, ranges, matrix dimensions and age are revalidated.
Default maximum age is 24 hours. For a deliberate later historical replay, append
an explicit age limit, for example `--max-recording-age-seconds 315360000` for a
ten-year demo window. This does not change retrieval times or make the data live.
Tests freeze the adapter clock at capture time without weakening production age
checks.

For a fresh live run using the locally configured ORS key:

```powershell
uv run --project packages/geo --env-file .env python scripts/geo_smoke.py --all-anchors --mode live --recordings-dir data/tmp/anchors-live/recordings --output-dir data/tmp/anchors-live/demo
```

The `manifest.json` `anchor_ids` define the matrix row and column order:
`mega_silk_way`, `botanical_garden`, `expo_nur_alem`, `nurzhol_boulevard`.
Follow only files attached to successful checks. Failures retain error codes and
`result=null`; missing routes never become straight lines or speed estimates.

Mega E/F are OSM-mapped entrances, not independently surveyed entrances. EXPO and
the garden remain representative bounding-box centers with unknown entrances.
Nurzhol uses the Nurzhol–Keruen guidepost node. Snapping does not prove a walkable
connection from any original coordinate. Opening status, wheelchair access,
current restrictions and covered passages remain unverified. The ORS graph's
underlying OSM date is 13 September 2026, earlier than the current OSM retrieval.

Keep **openrouteservice.org | OpenStreetMap contributors** visible in downstream
maps. Source data uses the [OSM license](https://www.openstreetmap.org/copyright).
Detailed coordinates, sources and results are in the
[Developer 1 report](../../../docs/developer-1-anchors-report.md).
