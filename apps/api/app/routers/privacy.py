from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.schemas.privacy import H3ResolveRequest, H3ResolveResponse
from app.services.privacy_service import PrivacyService

router = APIRouter(prefix="/api/v1/privacy", tags=["privacy"])


def get_privacy_service(request: Request) -> PrivacyService:
    service: PrivacyService = request.app.state.privacy_service
    return service


@router.post(
    "/resolve-h3",
    response_model=H3ResolveResponse,
    summary="Resolve a resolution-8 H3 cell to an approximate nearby catalog anchor",
    description="Send only a client-generated H3 cell ID in the JSON body. "
    "GPS fields and query parameters are rejected. Unsupported areas return "
    "no_nearby_anchor. H3 reveals an approximate area and does not guarantee anonymity.",
)
def resolve_h3(
    request: H3ResolveRequest,
    http_request: Request,
    response: Response,
    service: Annotated[PrivacyService, Depends(get_privacy_service)],
) -> H3ResolveResponse:
    if http_request.query_params:
        raise HTTPException(
            status_code=422,
            detail="Query parameters are not supported",
            headers={"Cache-Control": "no-store"},
        )
    response.headers["Cache-Control"] = "no-store"
    return service.resolve(request)
