from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.schemas.routes import RoutePlanRequest, RoutePlanResponse
from app.services.route_planner import RoutePlanner

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])


def get_route_planner(request: Request) -> RoutePlanner:
    planner: RoutePlanner = request.app.state.route_planner
    return planner


@router.post("/plan", response_model=RoutePlanResponse)
def plan_route(
    request: RoutePlanRequest, planner: Annotated[RoutePlanner, Depends(get_route_planner)]
) -> RoutePlanResponse:
    return planner.plan(request)
