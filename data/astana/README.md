# Astana POI snapshot

Actual OpenStreetMap data collected through `https://overpass-api.de/api/interpreter`.
This directory contains a real source capture and its deterministic JSON / GeoJSON
exports. It is not a synthetic demo dataset or a live business directory.

- Downloaded: **2026-10-19 19:07:30 Asia/Qyzylorda** (14:07:30 UTC).
- OSM database timestamp: **2026-10-19 14:05:36 UTC**.
- Bounds: south 51.075, west 71.385, north 51.145, east 71.455.
- Source objects: **501**; retained POIs: **497**; excluded: **4**.
- Missing names: **227**; missing hours: **401**; unknown indoor status: **490**.
- Approximate way/relation bounding-box centers: **256**. These are not verified entrances.

Retained categories include 97 cafes, 75 restaurants, 40 fast-food objects,
147 playgrounds, 49 gardens, 24 parks, 11 malls, and other supported OSM categories.
Counts refer to OSM objects; potentially duplicate representations across different
OSM identities are not automatically merged. A POI's presence does not confirm
that it is open now, accessible, suitable for a particular user, or reachable on foot.

Validate all three files from the repository root:

```powershell
uv run --project packages/data_pipeline python scripts/validate_data.py data/astana/pois.json --raw data/astana/overpass.capture.json --geojson data/astana/pois.geojson
```

The validator checks the recorded source hash, rebuilds every normalized POI, and
compares the complete GeoJSON export. The pipeline README describes collection,
offline replay, field evidence, and the provisional dataset format.

**© OpenStreetMap contributors.** This database is available under the
[Open Database License (ODbL)](https://www.openstreetmap.org/copyright).
Preserve attribution and applicable database-license obligations when reusing it.
