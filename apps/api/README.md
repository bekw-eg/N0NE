# VibeRoute backend

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required. From the repository root:

```sh
cd apps/api
uv sync --python 3.11
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

The source checkout must include `data/astana/pois.json`. Local editable dependencies
resolve from `packages/data_pipeline` and `packages/geo`. No Overpass, ORS, secret,
or internet access is needed at runtime. Startup fails clearly if Dataset validation
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

Tests use the committed 497 real POIs and no network. The existing `geo_adapter.py`
facade stays available for a future planner; POI search does not call ORS.
