from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.core.errors import install_error_handlers
from app.repositories.poi_repository import POIRepository
from app.routers import health, pois
from app.services.poi_service import POIService


def create_app(
    settings: Settings | None = None,
    repository: POIRepository | None = None,
) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        loaded = repository or POIRepository.load(config.poi_dataset_path)
        application.state.poi_service = POIService(loaded)
        yield

    application = FastAPI(title="VibeRoute POI API", version="0.1.0", lifespan=lifespan)
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
    return application


app = create_app()
