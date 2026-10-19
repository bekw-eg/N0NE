from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.schemas.weather import WeatherQuery, WeatherResponse
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])


def get_weather_service(request: Request) -> WeatherService:
    service: WeatherService = request.app.state.weather_service
    return service


@router.get("", response_model=WeatherResponse)
def get_weather(
    query: Annotated[WeatherQuery, Query()],
    service: Annotated[WeatherService, Depends(get_weather_service)],
) -> WeatherResponse:
    return service.get_weather(query.start_anchor_id)
