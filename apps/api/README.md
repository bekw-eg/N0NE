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

## Retrieval and local Qwen

`POST /api/v1/retrieval/search` and `POST /api/v1/rag/query` accept
`{"query":"Ботаникалық бақ","top_k":5,"language":"kk"}`. The query is limited
to 1000 characters, `top_k` to 1–10, and the JSON body to 16 KiB. Language is
optional (`ru`, `kk`, `en`); short ambiguous phrases can use an explicit language.
See the [Developer №3 integration guide](../../docs/developer-3-api-integration.md)
for full response examples and fallback handling, and the
[retrieval architecture](../../docs/retrieval-rag.md) for grounding guarantees.

The default search is BM25, explicitly reported as `lexical`. To run entirely
without models, export `LLM_PROVIDER=disabled` and `SEMANTIC_ENABLED=false`.
Normal POI API startup never contacts Overpass or ORS. Semantic indexing contacts
only the configured embedding service when explicitly enabled.

Install [Ollama](https://ollama.com/) and pull the exact models:

```sh
ollama pull qwen3:4b-instruct
ollama pull qwen3-embedding:0.6b
```

Export variables shown in [.env.example](.env.example), or copy it to `.env` and
explicitly load it using `uv run uvicorn app.main:app --env-file .env --no-access-log`.
No `.env` is read implicitly. The required model identifiers are configurable:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen3:4b-instruct
EMBEDDING_MODEL=qwen3-embedding:0.6b
SEMANTIC_ENABLED=true
```

Before starting the server, warm the index (optional):

```sh
uv run python scripts/build_index.py
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In PowerShell use `$env:SEMANTIC_ENABLED='true'` and `$env:LLM_PROVIDER='ollama'`.
Index files default to ignored `data/tmp/embeddings`, separate from source POIs.
An unavailable embedding model produces `retrieval_mode=lexical` and a warning;
an unavailable or invalid LLM produces `generation_status=retrieval_only`.
Neither condition makes the POI API unavailable. Restart to retry an index build
that failed at startup; a failed query embedding is retried on the next request.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SEMANTIC_ENABLED` | `false` | Explicit embedding/index opt-in |
| `LLM_PROVIDER` | `ollama` | `ollama` or `disabled` |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Server-side provider endpoint |
| `EMBEDDING_MODEL` | `qwen3-embedding:0.6b` | Cache model identifier |
| `LLM_MODEL` | `qwen3:4b-instruct` | Chat model |
| `EMBEDDING_INDEX_DIR` | checkout `data/tmp/embeddings` | Derived cache directory |
| `EMBEDDING_BATCH_SIZE` | `32` | 1–128 source documents per embed call |
| `EMBEDDING_TIMEOUT_SECONDS` | `60` | Per-call timeout, max 120 |
| `INDEX_BUILD_TIMEOUT_SECONDS` | `300` | Deadline checked between batches, max 600 |
| `LLM_TIMEOUT_SECONDS` | `60` | Per-call timeout, max 120 |
| `LLM_MAX_TOKENS` | `1200` | 100–4096 output tokens, temperature zero |
| `SEMANTIC_MIN_SCORE` | `0.35` | Cosine candidate threshold, not factual confidence |
| `CONTEXT_MAX_BYTES` | `24000` | UTF-8 evidence limit, 1024–64000 |

The index deadline may be exceeded by at most one in-flight request timeout.
Cold model loads and CPU indexing can take minutes; the explicit build command
keeps that cost out of application readiness. No call retries indefinitely.

Additional checks:

```sh
uv run mypy app scripts
uv run python scripts/smoke.py
uv run python scripts/ollama_smoke.py
```

`smoke.py` starts a real local Uvicorn server with the current environment.
For a reproducible model-free smoke set `LLM_PROVIDER=disabled` and
`SEMANTIC_ENABLED=false`. `ollama_smoke.py` requires both real models, verifies
hybrid retrieval and grounded Kazakh output, returns 0 on success, 1 on failure,
and 2 when skipped because a model/service is unavailable. Mock unit tests never
use the network; real-model success is reported separately.
