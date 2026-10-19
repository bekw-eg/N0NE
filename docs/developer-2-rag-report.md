# Developer №2 — PR B

Branch: `feature/backend-rag`. Base: `feature/backend-poi-api` while PR A is open.
PR A: <https://github.com/bekw-eg/N0NE/pull/5>, commit
`b77a3f9faff8cfc84d8f4ba3d891d42a56c1798f`.
Commit subject: `feat(rag): implement grounded retrieval and Qwen integration`.
The PR B URL and final commit SHA are recorded in the delivery message.

## Delivered

- `POST /api/v1/retrieval/search` and `POST /api/v1/rag/query`; existing POI,
  health, docs and OpenAPI endpoints remain available.
- Unicode BM25 over actual source fields and category taxonomy translations.
- Optional batch Ollama embeddings, cosine ranking, validated atomic local
  index keyed by exact dataset hash/model/text version, and RRF hybrid ranking.
- Explicit lexical fallback on disabled/unavailable embeddings; complete source
  provenance, nullable values, OSM/ODbL metadata and factual caveats in responses.
- Bounded evidence context and replaceable provider protocols; local Qwen chat
  with JSON Schema, temperature zero, token/time limits and safe error codes.
- Constrained extractive generation: the LLM selects real evidence IDs and copies
  approved explanations. Server checks schema, language, membership, duplicates
  and exact explanation equality. Invalid output falls back to retrieval-only.
- Input/body limits, no raw GPS field, no prompt or location logs, and mock-only
  tests that fail if real network access is attempted.
- Complete setup, architecture, frontend integration and real-record examples.

## Changed files relative to PR A

```text
apps/api/.env.example
apps/api/README.md
apps/api/app/core/body_limit.py
apps/api/app/core/config.py
apps/api/app/integrations/ollama.py
apps/api/app/main.py
apps/api/app/retrieval/__init__.py
apps/api/app/retrieval/lexical.py
apps/api/app/retrieval/semantic.py
apps/api/app/retrieval/text.py
apps/api/app/routers/retrieval.py
apps/api/app/schemas/rag.py
apps/api/app/services/evidence.py
apps/api/app/services/rag_service.py
apps/api/app/services/retrieval_service.py
apps/api/examples/rag-botanical-kk.json
apps/api/examples/retrieval-rafe.json
apps/api/scripts/build_index.py
apps/api/scripts/ollama_smoke.py
apps/api/scripts/smoke.py
apps/api/tests/conftest.py
apps/api/tests/test_rag.py
apps/api/tests/test_retrieval.py
apps/api/tests/test_semantic.py
docs/developer-2-rag-report.md
docs/developer-3-api-integration.md
docs/retrieval-rag.md
```

No source dataset, anchor, data/geo package, original geo facade or dependency
changes are included in this PR. The derived index is ignored, not committed.

## Executed verification

Windows, CPython 3.14.6, current uv lockfile:

| Check | Result |
| --- | --- |
| `uv run pytest -q` | 89 passed, all real HTTP blocked |
| Existing data/geo/integration tests | 117 passed |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | 36 files formatted |
| `uv run mypy app scripts` | passed, 30 source files |
| `uv lock --check --offline` | passed, 32 packages |
| Real Uvicorn smoke with models disabled | passed, lexical/retrieval-only |
| `uv run python scripts/build_index.py` | real model indexed all 497 POIs |
| Real Uvicorn with semantic + Qwen enabled | passed, hybrid/generated |
| `uv run python scripts/ollama_smoke.py` | passed with real models in kk and ru |

Real models: `qwen3-embedding:0.6b`, `qwen3:4b-instruct` on local Ollama.
Dataset SHA-256: `2d6fee7be9869561eee8f09a7c8927e69710f69cdbe9e463bf0d7536f2a2acf7`.
The cache contains 497 validated vectors, separately from `pois.json`.
Early cold/concurrent model attempts exceeded the initial 10/30-second limits
and correctly fell back. With bounded 60-second call limits and an explicit
index warm-up, the subsequent complete real-model checks passed. This does not
claim that the initial attempts passed or establish a general latency guarantee.

The same two upstream Starlette/httpx and AnyIO deprecation warnings as PR A
remain. Python 3.11 execution was not tested; code/lint/type targets are 3.11,
and the actual interpreter is within the project's Python >=3.11 requirement.

## Run and integration

```sh
cd apps/api
uv sync --python 3.11
ollama pull qwen3:4b-instruct
ollama pull qwen3-embedding:0.6b
```

Export `LLM_PROVIDER=ollama`, `SEMANTIC_ENABLED=true` (PowerShell:
`$env:LLM_PROVIDER='ollama'; $env:SEMANTIC_ENABLED='true'`), then:

```sh
uv run python scripts/build_index.py
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

For no-model operation export `LLM_PROVIDER=disabled` and `SEMANTIC_ENABLED=false`.
Use an installed Python >=3.11 if 3.11 cannot be downloaded. See
[setup](../apps/api/README.md), [architecture](retrieval-rag.md), and
[Developer №3 guide](developer-3-api-integration.md) for configuration and examples.

## Limits and PR handling

OSM is source evidence, not independent field verification. Wi-Fi, subjective
preferences, current opening, walking reachability/time/distance and routes are
not certified. Generation is deliberately extractive; arbitrary model prose is
rejected rather than being treated as verified facts. There is no product-level
relevance benchmark, morphological analyzer, authentication or request limiter.
Semantic indexing is opt-in and cold starts depend on local hardware.

PR B is stacked; merge order is A then B. No merge is performed by this work.
After PR A is merged, change PR B's base to `main` and inspect its diff. If A is
squash-merged rather than merged with its commit retained, rebase B's own commit
onto current main before pushing an updated branch and checking the diff.
