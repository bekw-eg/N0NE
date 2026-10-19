"""Explicit, opt-in live ORS smoke. Never print keys or provider diagnostics."""

import sys

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.routes import RoutePlanSuccess


def main() -> int:
    settings = Settings(semantic_enabled=False, llm_provider="disabled")
    if settings.ors_api_key is None or not settings.ors_api_key.get_secret_value().strip():
        print("SKIP: no ORS_API_KEY in the environment")
        return 2
    application = create_app(settings)
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/routes/plan",
            json={
                "start_anchor_id": "expo_nur_alem",
                "duration_minutes": 60,
                "query": "Хочу спокойную прогулку возле EXPO",
                "round_trip": True,
                "language": "ru",
            },
        )
        if response.status_code != 200:
            print(f"FAIL: HTTP {response.status_code}")
            return 1
        result = response.json()
        if result["status"] != "success":
            print(f"FAIL: no_route ({result['reason']})")
            return 1
        route = RoutePlanSuccess.model_validate(result)
        assert route.routing_provenance.directions is not None
        assert route.routing_provenance.directions.mode == "live"
        repository = application.state.route_planner.retrieval.repository
        assert all(stop.id in repository.by_id for stop in route.stops)
        assert len(route.route_geojson.features[0].geometry.coordinates) > 2
        print(
            f"PASS: live ORS, stops={len(route.stops)}, "
            f"walking_minutes={route.walking_minutes:.2f}, "
            f"visiting_minutes={route.visiting_minutes:.0f}, "
            f"total_minutes={route.estimated_total_minutes:.2f}, "
            f"distance_meters={route.total_distance_meters:.1f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
