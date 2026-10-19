# VIBEROUTE — DEVELOPMENT REPORT

Developer Role: **1 — Data & Geo Engineer**

GitHub Login: `bekw-eg` (active GitHub CLI account; repository permission `ADMIN`).

Git Author Name: `bekw-eg`, read from the existing global Git configuration.

Git Author Email: configured, address withheld. GitHub associates both the author
and committer of the published bootstrap and implementation commits with
`bekw-eg`. The configured email was also found on existing commits associated
with that account. No identity settings or author environment overrides were changed.

Branch: `feature/data-geo-poi-collector`, tracking the published origin branch.
Base branch: `main`, initialized with the owner's explicit approval.

Implemented:

- Bounded Overpass `nwr` collection with actual POST requests, metadata/centers,
  three-attempt HTTP/transport retry, and controlled errors for incomplete payloads.
- Pydantic v2 validation; deterministic normalization, exact-identity deduplication,
  explicit unknown attributes, provenance/tag evidence, and quality warnings.
- JSON and GeoJSON point exports, raw-capture SHA-256, deterministic source replay,
  and complete GeoJSON validation.
- Actual Astana capture: 501 OSM objects, 497 retained POIs, 4 excluded.
- Package lockfile, CLI entry points, root wrapper scripts, and integration notes.
- JSON/GeoJSON LF attributes so capture hashes survive Windows Git checkouts.
- Configured the previously missing `origin` as `https://github.com/bekw-eg/N0NE.git`.
- Published the approved two-file bootstrap, then the collector on a feature branch.
- Opened PR #1 to `main`; the PR remains open for owner review.

Files Changed (all new):

- Approved bootstrap: `README.md`, `.gitignore`.
- `.gitattributes`.
- `packages/data_pipeline/pyproject.toml`, `uv.lock`, `README.md`.
- `packages/data_pipeline/src/viberoute_data/{__init__,models,overpass,normalize,cli}.py`.
- `packages/data_pipeline/tests/{conftest,test_normalize,test_overpass,test_cli}.py`.
- `scripts/collect_data.py`, `scripts/validate_data.py`.
- `data/astana/{README.md,overpass.capture.json,pois.json,pois.geojson}`.
- This report: `docs/developer-1-report.md`.

Tests Executed:

```powershell
uv sync --project packages/data_pipeline --group dev
uv run --project packages/data_pipeline pytest packages/data_pipeline/tests -q
uv run --project packages/data_pipeline ruff check packages/data_pipeline scripts
uv run --project packages/data_pipeline ruff format --check packages/data_pipeline scripts
uv run --project packages/data_pipeline mypy --config-file packages/data_pipeline/pyproject.toml packages/data_pipeline/src
uv run --project packages/data_pipeline python scripts/collect_data.py --bbox 51.075 71.385 51.145 71.455 --output-dir data/astana
uv run --project packages/data_pipeline python scripts/validate_data.py data/astana/pois.json --raw data/astana/overpass.capture.json --geojson data/astana/pois.geojson
uv run --project packages/data_pipeline python scripts/collect_data.py --from-raw data/astana/overpass.capture.json --output-dir data/tmp/replayed
git -c core.autocrlf=true checkout-index --all --prefix=data/tmp/windows-checkout/
uv run --project packages/data_pipeline python scripts/validate_data.py data/tmp/windows-checkout/data/astana/pois.json --raw data/tmp/windows-checkout/data/astana/overpass.capture.json --geojson data/tmp/windows-checkout/data/astana/pois.geojson
```

Tests Result:

- **39 passed** on CPython **3.14.0**. Tests cover HTTP failures/retries, partial
  responses, malformed coordinates/identity, private and disused objects,
  conflicting duplicates, unknown attributes, evidence integrity, and CLI failures.
- Ruff lint and format checks passed; strict mypy passed for all five source files.
- Actual Overpass request returned HTTP 200; source-backed validation passed for 497 POIs.
- All three replayed files were compared to the captured dataset: **byte-identical**.
- Checked that mapper usernames/user IDs are absent from the capture.
- Source-backed validation passed after a Windows-style `core.autocrlf=true` checkout.
- Python 3.11+ is declared; execution on 3.11 itself has not been tested.

Commit SHA (implementation): `828f5fb7b0d0201fd28782b11986c0201a6d1c14`.

Bootstrap SHA: `fd6bd8be000816239f2ae88b975d34a3372c2b7d`.

Push Status: **successful** for the approved initial `main` and the feature branch.

Pull Request URL: https://github.com/bekw-eg/N0NE/pull/1 (open, ready for review).

This report is delivered in a separate documentation commit on the same PR;
the implementation SHA above identifies the tested code and dataset.

Integration Notes:

- Dataset format `0.1.0` is internal and provisional. Developer 2 must agree its
  mapping to the shared POI contract; no backend contracts were created or changed.
- Missing names/hours/indoor status remain null. Facts are source assertions and
  include their OSM URLs and exact source tags.
- GeoJSON contains points in longitude/latitude order; it contains no routes.
- Data license and attribution are included in dataset metadata and documentation.

Known Limitations:

- PR #1 has not been merged; no automatic merge or further direct commits to `main`
  were performed. The approved bootstrap includes only `README.md` and `.gitignore`.
- 401 POIs lack opening hours; 490 lack explicit indoor evidence; 256 use
  approximate centers. No absent properties have been inferred.
- Similar node/way objects with different OSM identities are retained for review.
- ORS, Open-Meteo, H3, enrichment from other sources, and routing fixtures are not
  implemented in this first collector task. Backend/RAG/UI are outside this role.

Next Recommended Task:

- Owner review of PR #1; merge requires a separate owner decision.
- Agree the POI mapping with developer 2, then implement the ORS walking adapter
  with real isochrones, matrix, directions, and recorded route fixtures.
