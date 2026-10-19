# Retrieval and grounded explanations

## Data and ranking

`POIRepository` is shared by the POI API and retrieval; its validated snapshot
is loaded once. No new POIs or source attributes are fabricated. The original
dataset, geographic packages and Developer №1's anchors are never rewritten.

1. Normalize query text with Unicode NFKC and `casefold`; tokenize Unicode letters
   and digits (Russian and Kazakh included).
2. Build BM25 (k1=1.5, b=0.75) from real names, localized names, categories,
   addresses and a narrow allowlist of OSM tags (`brand`, `cuisine`,
   `internet_access`, `outdoor_seating`) plus non-null indoor/covered/wheelchair
   source attributes. Freeform `note` and `description` tags are excluded.
3. Category translations in `retrieval/text.py` are taxonomy aliases, not new
   descriptions of the place. BM25 is token-based, not a morphological analyzer;
   arbitrary inflections and paraphrases may require semantic retrieval.
4. Optionally batch the same source text through Ollama `/api/embed`. Check
   vector counts, consistent dimensions, finite values and non-zero norm.
   Normalize vectors and score queries by cosine similarity. Filter candidates
   at the configured threshold, which is not a truth/confidence probability.
5. When semantic retrieval succeeds, fuse both rankings by
   `sum(1 / (60 + rank))` (Reciprocal Rank Fusion). Deduplicate by stable OSM ID;
   break ties by ID. Lexical-only responses use BM25 scores and say `lexical`.
   Hybrid responses use RRF scores with the component scores retained.

The optional JSON vector cache includes format version, exact dataset SHA-256,
embedding model ID, text extraction version, source-text hash, IDs and vectors.
A changed dataset/model or incompatible/corrupt cache triggers a rebuild. Writes
use an atomic temporary-file replacement. An unwritable cache still allows an
in-memory index and emits `embedding_cache_write_failed`. Partial failed builds
are not published. An empty source snapshot produces no invented results.
No vector database or numerical/ML dependency is necessary for 497 records.

Semantic retrieval is an explicit opt-in (`SEMANTIC_ENABLED=true`). Disabled,
failed-startup, and failed-query states emit distinct warning codes. If embedding
fails, the response reports `lexical`; semantic behavior is never silently claimed.
Cached vectors do not remove the need to embed the query. Restart after a failed
startup build to retry; query failures do not discard an otherwise valid index.
Changing model weights under the same tag is not detected automatically: use a
new model ID or remove the derived cache after such a change.

## Evidence and generation

Build context from at most 10 retrieved POIs, bounded by UTF-8 byte size (24 KiB
by default). It includes IDs, real names, category, address, source hours,
nullable source attributes, URL, retrieval timestamp and quality warnings.
It excludes coordinates and the rest of the dataset. If a whole source record
cannot fit, omit that record and report `evidence_context_truncated`; never turn
a truncated value into an asserted fact.

The separate `EmbeddingProvider` and `LLMProvider` protocols allow provider
replacement without rewriting retrieval. The Ollama implementation uses
[`/api/embed`](https://docs.ollama.com/api/embed) for batches and
[`/api/chat`](https://docs.ollama.com/api/chat) with a Pydantic JSON Schema in
`format`, `stream=false`, temperature zero, bounded output and a timeout.
No provider errors or submitted prompts are logged or echoed as diagnostics.

This implementation deliberately uses **constrained extractive generation**.
The server prepares safe Russian, Kazakh or English explanation choices for
each evidence ID. Qwen selects/reorders a subset and copies its approved text.
The selected explanation describes the source category, whether source hours
exist, and the absence of current-open/walking verification. Raw OSM names,
addresses and hours stay in typed evidence fields and are never interpolated
into trusted prose. The response summary is rendered by the server.

After schema validation the server checks language, ID membership in this exact
context, no duplicates, and exact equality of every explanation to the allowed
text for that ID. Extra fields, unknown IDs, arbitrary prose or unsupported
claims reject the entire draft. Return a deterministic retrieval-only answer
with a machine-readable warning instead. An empty context never invokes Qwen.
This is more restrictive than freeform paraphrasing and should be visible to
clients through `generation_method=constrained_extractive` versus `deterministic`.
`generation_status=generated` means the model's structured selection was accepted;
it does not mean independent verification or unrestricted authorship of the prose.

JSON Schema alone does **not** establish factual grounding. Prompt instructions
alone do not reliably prevent injection either. User text and OSM fields are
serialized as untrusted data in a separate message; the model has no tools or
external browsing. Server-side membership and exact-text checks enforce the
accepted output boundary even when a prompt injection changes model behavior.

## Limits of factual claims

- Every recommendation is an ID from the bounded retrieved context. Sources and
  full original provenance remain available in the response.
- Indoor, hours, covered and wheelchair values are OSM source statements;
  `null` is unknown and is never filled from category or model knowledge.
- A source `internet_access` tag may affect retrieval relevance; this release
  does not certify Wi-Fi, coziness, quietness or other requested preferences.
- Presence of source hours is not a current-open verdict. Centers are not
  entrances; scores are not factual confidence; EXPO text does not prove proximity.
- There are no ORS HTTP calls, walking times, distances, multi-stop plans, weather
  or H3 operations in this engine. A future planner must independently verify
  reachability and current access before making those claims.
- Language auto-detection uses distinctive Kazakh characters, then Cyrillic for
  Russian and English otherwise. Pass `language` for ambiguous short queries.
- Runtime authentication, request rate limiting and a product-level relevance
  evaluation corpus are future work. Limit public access at deployment as needed.

## Verification

Unit tests block real HTTP transport and use `httpx.MockTransport` plus provider
doubles. They cover real Russian/Kazakh POIs, unknown values, empty responses,
RRF, finite/dimensional vector checks, batching, cache invalidation, corruption,
model failures/timeouts, invalid JSON/IDs, unsupported text, duplicate IDs and
user/OSM injection. Security mutations are in-memory test data only. The source
dataset hash stays unchanged. The optional real-model smoke has its own exit
status and must not be confused with mock test results.
