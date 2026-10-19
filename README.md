# VibeRoute

Context-aware urban micro-routes for Astana. Development is split between data
and geography (developer 1), backend and RAG (developer 2), and web UX (developer 3).

The first component is the [OpenStreetMap data pipeline](packages/data_pipeline/README.md).
It collects source-backed POIs and exports validated JSON and GeoJSON. The
[ORS geo adapter](packages/geo/README.md) provides walking routes, 10/15-minute
isochrones, time/distance matrices, and recorded-response replay. Weather,
backend recommendations, and the web application are subsequent tasks.

The [four-zone anchor report](docs/developer-1-anchors-report.md) documents current
OSM evidence, mapped versus unknown entrances, real HeiGIT walking checks, and the
[offline geographic demo](data/geo/anchors/README.md).

Contributions target `main` through feature branches and pull requests.
