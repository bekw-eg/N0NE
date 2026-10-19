# VibeRoute

Context-aware urban micro-routes for Astana. Development is split between data
and geography (developer 1), backend and RAG (developer 2), and web UX (developer 3).

The first component is the [OpenStreetMap data pipeline](packages/data_pipeline/README.md).
It collects source-backed POIs and exports validated JSON and GeoJSON. The
[ORS geo adapter](packages/geo/README.md) provides walking routes, 10/15-minute
isochrones, time/distance matrices, and recorded-response replay. The
[FastAPI backend](apps/api/README.md) serves POIs, grounded retrieval/RAG,
ORS route planning, and anchor-based Open-Meteo weather with bounded TTL caching
and explicit unknown fallback. The web application is a subsequent task.

The [four-zone anchor report](docs/developer-1-anchors-report.md) documents current
OSM evidence, mapped versus unknown entrances, real HeiGIT walking checks, and the
[offline geographic demo](data/geo/anchors/README.md).

Contributions target `main` through feature branches and pull requests.

Weather: `GET /api/v1/weather?start_anchor_id=expo_nur_alem` supports the four
catalog anchors without user GPS. See the
[Developer №3 guide](docs/developer-3-api-integration.md#weather) for frontend
integration, timestamps, nullable indicators and warnings. Live checks are opt-in:
`cd apps/api` then `uv run python scripts/weather_smoke.py --all-anchors`.
