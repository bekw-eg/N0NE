# Developer №2 — PR A

Branch: `feature/backend-poi-api`, based on `origin/main` at
`793e5adebbadb876c2e1cc349bb00b5196f73bd6`. Commit subject:
`feat(api): implement FastAPI foundation and POI search`.
The PR URL and final commit SHA are recorded in the delivery message.

## Delivered

- `GET /health`, `GET /api/v1/pois`, `GET /api/v1/pois/{poi_id}`.
- Interactive `/docs` and `/openapi.json`.
- One startup validation using the existing `viberoute_data.models.Dataset`;
  497 POIs, stable ordering, indexed IDs, Unicode search, category and pagination.
- Public contract in `contracts/poi.schema.json`, complete original provenance,
  explicit OSM-only verification, nullable source fields and ODbL attribution.
- Explicit CORS origins, bounded parameters, dependency injection and safe 422s.
- Standalone API uv project, local package dependencies, lockfile, environment
  example, install/run/integration guide and real-process HTTP smoke script.

The files added are under `apps/api/` (app core, models, repository, service,
routers, dependencies, tests, scripts, configuration and README), `contracts/`
and this report. Existing geographic/data code, datasets and anchors are unchanged.
Developer №1's worktree and open PR #4 are preserved.

## Executed verification

On Windows, CPython 3.14.6 (the project supports Python >=3.11):

| Check | Result |
| --- | --- |
| `uv sync --python C:\\Python314\\python.exe --offline` | passed, 32 packages |
| `uv run pytest -q` | 22 passed |
| Existing data/geo and integration tests | 117 passed |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | 20 files formatted |
| `uv run mypy app scripts` | 17 source files, passed |
| `uv run python scripts/smoke.py` | real Uvicorn HTTP passed |

The test client emitted two upstream deprecation warnings (Starlette/httpx and
AnyIO); no tests failed. Python 3.11 could not be downloaded during this run;
execution on that interpreter is not claimed. Ruff/mypy target Python 3.11.

## Run and limitations

```sh
cd apps/api
uv sync --python 3.11
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Use an installed Python >=3.11 if downloading 3.11 is unavailable. See
[`apps/api/README.md`](../apps/api/README.md) for request examples and contract
mapping. Restart after replacing a dataset. There is no current opening-state
verification, route planner, proximity calculation, authentication or rate limiter.
OSM statements remain source claims. No PR is merged automatically.
