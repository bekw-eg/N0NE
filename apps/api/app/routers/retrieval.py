from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.schemas.rag import RAGResponse, RetrievalResponse, SearchRequest
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/api/v1", tags=["retrieval", "rag"])


def get_retrieval_service(request: Request) -> RetrievalService:
    service: RetrievalService = request.app.state.retrieval_service
    return service


def get_rag_service(request: Request) -> RAGService:
    service: RAGService = request.app.state.rag_service
    return service


@router.post("/retrieval/search", response_model=RetrievalResponse)
def search(
    request: SearchRequest,
    service: Annotated[RetrievalService, Depends(get_retrieval_service)],
) -> RetrievalResponse:
    return service.search(request)


@router.post("/rag/query", response_model=RAGResponse)
def query(
    request: SearchRequest,
    service: Annotated[RAGService, Depends(get_rag_service)],
) -> RAGResponse:
    return service.query(request)
