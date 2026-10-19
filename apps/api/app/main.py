from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.body_limit import BodyLimitMiddleware
from app.core.config import Settings
from app.core.errors import install_error_handlers
from app.integrations.ollama import EmbeddingProvider, LLMProvider, OllamaEmbeddings, OllamaLLM
from app.repositories.poi_repository import POIRepository
from app.routers import health, pois, retrieval
from app.services.poi_service import POIService
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievalService


def create_app(
    settings: Settings | None = None,
    repository: POIRepository | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    llm_provider: LLMProvider | None = None,
) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        loaded = repository or POIRepository.load(config.poi_dataset_path)
        application.state.poi_service = POIService(loaded)
        with httpx.Client(trust_env=False) as client:
            embedding = embedding_provider
            if embedding is None and config.semantic_enabled:
                embedding = OllamaEmbeddings(config, client)
            llm = llm_provider
            if llm is None and config.llm_provider == "ollama":
                llm = OllamaLLM(config, client)
            search = RetrievalService(loaded, config, embedding)
            application.state.retrieval_service = search
            application.state.rag_service = RAGService(search, config, llm)
            yield

    application = FastAPI(title="VibeRoute POI API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(BodyLimitMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    install_error_handlers(application)
    application.include_router(health.router)
    application.include_router(pois.router)
    application.include_router(retrieval.router)
    return application


app = create_app()
