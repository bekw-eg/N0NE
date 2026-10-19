from typing import Annotated

from fastapi import Depends, Request

from app.services.poi_service import POIService


def get_poi_service(request: Request) -> POIService:
    service: POIService = request.app.state.poi_service
    return service


POIServiceDep = Annotated[POIService, Depends(get_poi_service)]
