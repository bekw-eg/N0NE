# VibeRoute

Context-aware urban micro-routes for Astana. Development is split between data
and geography (developer 1), backend and RAG (developer 2), and web UX (developer 3).

The first component is the [OpenStreetMap data pipeline](packages/data_pipeline/README.md).
It collects source-backed POIs and exports validated JSON and GeoJSON. Routing,
weather, backend recommendations, and the web application are subsequent tasks.

Contributions target `main` through feature branches and pull requests.
