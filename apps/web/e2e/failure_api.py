"""Test-only FastAPI servers with simulated upstream ORS/Open-Meteo failures.

Production routers, schemas, adapter, planner and dataset are unchanged.
No real ORS credentials or external network requests are used here.
"""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / path) for path in (
    "apps/api", "packages/geo/src", "packages/data_pipeline/src",
)]

import httpx
import uvicorn
from app.core.config import Settings
from app.integrations.geo_adapter import GeoAdapter
from app.integrations.open_meteo import OpenMeteoClient
from app.main import create_app
from app.services.weather_service import WeatherService

scenario, port = sys.argv[1], int(sys.argv[2])


def ors_response(request):
    return httpx.Response(
        400 if scenario == "unreachable" else 403,
        json={"error": {"code": 2010 if scenario == "unreachable" else 403,
                        "message": "Simulated upstream failure"}},
    )


def weather_response(request):
    raise httpx.ConnectError("Simulated weather outage", request=request)


settings = Settings(semantic_enabled=False, llm_provider="disabled")
with (
    httpx.Client(transport=httpx.MockTransport(ors_response)) as ors,
    httpx.Client(transport=httpx.MockTransport(weather_response)) as weather,
):
    app = create_app(
        settings,
        geo_adapter=GeoAdapter(api_key="synthetic-test-only", client=ors),
        weather_service=WeatherService(OpenMeteoClient(weather), settings),
    )
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
