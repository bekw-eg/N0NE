"""Opt-in live Open-Meteo check through the real FastAPI endpoint (no fixed weather)."""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import get_args

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.weather import WEATHER_TZ, WeatherAnchorID, WeatherResponse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-anchors", action="store_true")
    parser.add_argument(
        "--output", type=Path, help="Save validated real endpoint responses as JSON"
    )
    args = parser.parse_args()
    anchors: tuple[WeatherAnchorID, ...] = (
        get_args(WeatherAnchorID) if args.all_anchors else ("expo_nur_alem",)
    )
    settings = Settings(semantic_enabled=False, llm_provider="disabled")
    results: list[dict[str, object]] = []
    failed = False
    with TestClient(create_app(settings)) as api:
        for anchor in anchors:
            response = api.get("/api/v1/weather", params={"start_anchor_id": anchor})
            if response.status_code != 200:
                print(f"FAIL: {anchor}, HTTP {response.status_code}")
                failed = True
                continue
            result = WeatherResponse.model_validate(response.json())
            print(result.model_dump_json(indent=2))
            results.append(result.model_dump(mode="json"))
            if result.status != "available":
                print(f"FAIL: {anchor}, weather is unknown ({','.join(result.warnings)})")
                failed = True
                continue
            assert result.source == "open-meteo" and result.anchor_id == anchor
            assert result.cache_status == "miss"
            assert (
                timedelta(0) <= datetime.now(WEATHER_TZ) - result.fetched_at < timedelta(minutes=1)
            )
            cached = WeatherResponse.model_validate(
                api.get("/api/v1/weather", params={"start_anchor_id": anchor}).json()
            )
            # At the hour boundary the service intentionally refreshes the hourly interval.
            if result.forecast_valid_at and datetime.now(WEATHER_TZ) >= result.forecast_valid_at:
                assert cached.status == "available"
            else:
                assert cached.cache_status == "hit" and cached.fetched_at == result.fetched_at
            print(f"PASS: {anchor}, live schema/provenance and immediate cache check")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
