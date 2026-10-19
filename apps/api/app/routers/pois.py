from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.dependencies import POIServiceDep
from app.schemas.poi import Category, POIPage, PublicPOI

router = APIRouter(prefix="/api/v1/pois", tags=["pois"])


@router.get("", response_model=POIPage)
def search_pois(
    service: POIServiceDep,
    q: Annotated[str, Query(max_length=200)] = "",
    category: Category | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> POIPage:
    return service.search(q, category, limit, offset)


@router.get("/{poi_id}", response_model=PublicPOI)
def get_poi(
    poi_id: Annotated[str, Path(max_length=80)],
    service: POIServiceDep,
) -> PublicPOI:
    poi = service.get(poi_id)
    if poi is None:
        raise HTTPException(status_code=404, detail="POI not found")
    return poi
