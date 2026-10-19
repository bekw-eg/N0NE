# VibeRoute OSM data pipeline (developer 1)

Collect actual POIs, preserve OSM evidence, and export JSON plus GeoJSON points.
Python 3.11+ and `uv` are required for the commands below. Run from the repository
root; no API key is required. This package does not start the backend or web UI.

```powershell
uv sync --project packages/data_pipeline --group dev
uv run --project packages/data_pipeline python scripts/collect_data.py --bbox 51.075 71.385 51.145 71.455 --output-dir data/astana
uv run --project packages/data_pipeline python scripts/validate_data.py data/astana/pois.json --raw data/astana/overpass.capture.json --geojson data/astana/pois.geojson
```

The study rectangle covers the EXPO / Mega Silk Way / Botanical Garden /
Water-Green Boulevard corridor. It is a collection boundary, not a walkability
claim, an isochrone, or an administrative boundary. Objects whose representative
point falls outside the rectangle are excluded. `--endpoint` selects another
Overpass instance explicitly; the collector does not silently switch sources.

To replay the checked-in source without a network request:

```powershell
uv run --project packages/data_pipeline python scripts/collect_data.py --from-raw data/astana/overpass.capture.json --output-dir data/tmp/replayed
```

Outputs:

- `overpass.capture.json`: recorded Overpass response, endpoint, exact query,
  retrieval timestamp, and bbox; mapper usernames/user IDs are removed.
- `pois.json`: a versioned dataset, source SHA-256, collection counts, and POIs.
- `pois.geojson`: point FeatureCollection using **longitude, latitude** order.

The Pydantic models in `src/viberoute_data/models.py` are an internal, provisional
dataset format (`0.1.0`). They do not establish the backend API contract. Developer
2 should agree the mapping to `contracts/poi.schema.json` before integration.
`Dataset.model_json_schema()` exports the current internal schema.

Each POI has an OSM identity and URL, retained factual tags, category, coordinates,
optional name and hours, explicit attribute evidence, and quality warnings.
`provenance.field_tags` records which OSM keys produced each factual field.
`retrieved_at` means downloaded; `osm_updated_at` means the source object last
changed and does not certify when a business fact was verified. The source's
database timestamp is retained separately. These are OSM assertions, not an
independent audit of each venue's present condition.

Rules:

- Missing names, schedules, and attributes remain `null`. Unnamed playgrounds
  retain a null name; the pipeline never invents a venue name.
- Only explicit `indoor=yes/no` and `covered=yes/no` set those attributes. A cafe,
  mall, or building is not automatically considered indoors. `covered` is separate
  from `indoor`; neither proves a continuous covered walking route.
- Opening hours are preserved verbatim and are not evaluated here.
- Way/relation centers are bounding-box centers, not centroids or verified
  entrances. Their coordinate kind and warning are carried into GeoJSON.
- `access=no/private`, `disused=yes`, and `abandoned=yes` objects are excluded.
  This does not prove that remaining objects are open or publicly accessible now.
- Deduplication merges identical repeated **OSM identities** only. Conflicting
  records for the same identity fail collection. Similar node/way objects are
  retained for later review to avoid merging distinct nearby establishments.
- Invalid payloads, upstream runtime remarks (including partial query results),
  malformed coordinates, and empty usable datasets fail explicitly. HTTP retries
  are bounded to three attempts and 30 seconds per backoff.
- Validation recomputes the raw hash and deterministically rebuilds every POI
  from the capture; optional GeoJSON validation compares the complete export.
  A hash detects inconsistency, not malicious substitution of an entire capture.
- Files are written atomically individually after complete validation. Keep the
  three files together; source validation detects mixed collection generations.
- Repository attributes preserve LF endings for JSON/GeoJSON on Windows so the
  recorded source SHA-256 also validates after a fresh checkout.

Tests use synthetic objects clearly labeled `SYNTHETIC TEST` and mock HTTP. They
do not claim that those fixtures are real places. A checked-in real capture can
be validated and replayed offline with the commands above.

```powershell
uv run --project packages/data_pipeline pytest packages/data_pipeline/tests
uv run --project packages/data_pipeline ruff check packages/data_pipeline scripts
uv run --project packages/data_pipeline mypy --config-file packages/data_pipeline/pyproject.toml packages/data_pipeline/src
```

Data attribution: **© OpenStreetMap contributors**, available under the
[Open Database License](https://www.openstreetmap.org/copyright). Preserve this
attribution in downstream datasets and map UI. Collection follows the documented
[Overpass QL format](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL),
including bounded `nwr` queries and `out meta center`.

Next role-1 work: agree dataset mapping with developer 2; implement ORS walking
isochrones/matrix/routes, Open-Meteo, H3 helpers, and real routing fixtures. This
collector has no walking-time estimates, synthetic routes, weather, or GPS intake.
