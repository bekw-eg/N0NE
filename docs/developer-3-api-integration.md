# Backend integration — Developer №3

Start the service with the commands in [apps/api/README.md](../apps/api/README.md).
Use `http://127.0.0.1:8000` locally and configure `CORS_ORIGINS` to the exact
frontend origin. Read `/openapi.json` for all types or `/docs` for interactive
requests. JSON is UTF-8; use actual OSM IDs instead of deriving IDs from names.
There is no raw user-GPS input field or route-planning endpoint in this release.

## POI lookup

```http
GET /health
GET /api/v1/pois?q=Rafe&category=cafe&limit=20&offset=0
GET /api/v1/pois/osm:node:1843876259
```

Health returns `{"status":"ok"}`. POI search returns `items`, `total`, `limit`,
`offset`, `dataset`. Detail returns a public POI object. The
[public JSON schema](../contracts/poi.schema.json) and backend README document
the mapping from the original dataset. All 497 records are available; no matches
return `items: []`. Unknown IDs return 404 and invalid parameters return 422.
Ordering is stable by ID; search is a normalized substring search, not ranking.

## Retrieval

```js
const response = await fetch(`${apiBase}/api/v1/retrieval/search`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'Хочу кафе возле EXPO с Wi-Fi', top_k: 5, language: 'ru' }),
});
if (!response.ok) throw new Error(`Search failed: ${response.status}`);
const result = await response.json();
```

Shared request body: `query` is 1–1000 characters (non-whitespace), `top_k` is
1–10 (default 5), `language` is optional `ru|kk|en`. Unknown properties are
rejected: do not send latitude/longitude. Bodies over 16 KiB return 413.

The retrieval response has these fields:

| Field | Meaning |
| --- | --- |
| `query` | Original Unicode query |
| `retrieval_mode` | `lexical` (BM25) or `hybrid` (BM25 + embeddings + RRF) |
| `results` | Ranked hits: public `poi`, 1-based `rank`, `score`, component scores, warnings |
| `dataset` | Dataset hash, collection/capture provenance and OSM/ODbL metadata |
| `warnings` | Disabled/unavailable providers and factual limitations |

Component scores are nullable. BM25 and RRF scores have different scales;
neither is a probability or independent verification. `results: []` is normal.
For complete real-snapshot output see
[retrieval-rafe.json](../apps/api/examples/retrieval-rafe.json).

## RAG

```js
const response = await fetch(`${apiBase}/api/v1/rag/query`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'Ботаникалық бақ', top_k: 3, language: 'kk' }),
});
const result = await response.json();
```

The RAG response includes:

| Field | Meaning |
| --- | --- |
| `query`, `language`, `explanation` | Original query and safe localized summary |
| `mentioned_poi_ids` | IDs selected for display; each is in retrieved context |
| `recommendations` | `poi_id` and validated localized explanation per result |
| `sources` | Selected evidence with source URLs, retrieval times and unknown values |
| `generation_status` | `generated` or `retrieval_only` |
| `generation_method` | `constrained_extractive` or `deterministic` |
| `llm_model` | Attempted model, or `null` when no model was called |
| `warnings` | Generation/retrieval fallback and factual limitations |
| `retrieval` | Full retrieval response, including public POIs and original provenance |

The model chooses evidence-backed records and copies server-approved explanation
text. `generated` does not mean the facts were independently verified. If the
provider times out, is unavailable or emits invalid/ungrounded output, display
the safe `retrieval_only` answer normally and make its status visible. A non-null
`llm_model` with `retrieval_only` indicates an attempted but rejected/failed call.
With no evidence, recommendations and sources are empty and no model is called.
See [rag-botanical-kk.json](../apps/api/examples/rag-botanical-kk.json) for a
complete real-record response generated with models disabled.

Key machine-readable warnings include `semantic_disabled`, `embedding_unavailable`,
`embedding_timeout`, `embedding_dimension_mismatch`, `llm_disabled`, `llm_unavailable`,
`llm_timeout`, `llm_invalid_response`, `llm_ungrounded_response`,
`no_evidence_for_generation`, `evidence_context_truncated`. All responses also
carry factual caveats; per-hit warnings identify missing source attributes.
New warning codes may appear, so render an unknown code safely.

## Display and privacy

Render OSM names/addresses as escaped plain text; they are untrusted source data,
not markup or instructions. Preserve `null` as unknown. Do not display a missing
name as a real business name. Display “© OpenStreetMap contributors” linked to
the supplied copyright URL and preserve `ODbL-1.0` metadata when redistributing.
Show `osm_source_only` status and retrieval timestamp where freshness matters.

Do not turn a preference query into a verified badge (Wi-Fi, quiet, cozy, indoor).
Do not display “open now,” walking distance/time or a reachable-from-user claim
from these results. Those checks belong to future integrations. Treat center
coordinates as representative points rather than building entrances.
Avoid putting exact user locations or raw queries in analytics, URL/access logs,
or error reporting. Backend validation errors omit submitted inputs and provider
diagnostics; the API intentionally echoes the original query only in successful
retrieval/RAG responses. CORS is not authentication.
