"""Run after installing packages/data_pipeline (see that package's README)."""

from viberoute_data.cli import collect_main

if __name__ == "__main__":
    raise SystemExit(collect_main())
