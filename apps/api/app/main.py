from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.body_limit import BodyLimitMiddleware
from app.core.config import Settings
from app.core.errors import install_error_handlers
from app.integrations.geo_adapter import GeoAdapter
from app.integrations.ollama import EmbeddingProvider, LLMProvider, OllamaEmbeddings, OllamaLLM
from app.integrations.open_meteo import OpenMeteoClient
from app.repositories.poi_repository import POIRepository
from app.routers import health, pois, privacy, retrieval, routes, weather
from app.services.poi_service import POIService
from app.services.privacy_service import PrivacyService
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievalService
from app.services.route_planner import RoutePlanner, WalkingAdapter
from app.services.weather_service import WeatherService


def create_app(
    settings: Settings | None = None,
    repository: POIRepository | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    llm_provider: LLMProvider | None = None,
    geo_adapter: WalkingAdapter | None = None,
    weather_service: WeatherService | None = None,
) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        loaded = repository or POIRepository.load(config.poi_dataset_path)
        application.state.poi_service = POIService(loaded)
        application.state.privacy_service = PrivacyService(config)
        with (
            httpx.Client(trust_env=False) as client,
            httpx.Client(
                timeout=httpx.Timeout(
                    config.ors_timeout_seconds, connect=min(5, config.ors_timeout_seconds)
                ),
                trust_env=False,
            ) as geo_client,
            httpx.Client(trust_env=False, follow_redirects=False) as weather_client,
        ):
            embedding = embedding_provider
            if embedding is None and config.semantic_enabled:
                embedding = OllamaEmbeddings(config, client)
            llm = llm_provider
            if llm is None and config.llm_provider == "ollama":
                llm = OllamaLLM(config, client)
            search = RetrievalService(loaded, config, embedding)
            application.state.retrieval_service = search
            application.state.rag_service = RAGService(search, config, llm)
            walking = (
                geo_adapter
                if geo_adapter is not None
                else GeoAdapter(
                    api_key=config.ors_api_key.get_secret_value() if config.ors_api_key else None,
                    base_url=config.ors_base_url,
                    client=geo_client,
                )
            )
            application.state.route_planner = RoutePlanner(search, walking, config)
            application.state.weather_service = weather_service or WeatherService(
                OpenMeteoClient(
                    weather_client,
                    timeout_seconds=config.weather_timeout_seconds,
                    forecast_hours=config.weather_forecast_hours,
                ),
                config,
            )
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
    application.include_router(routes.router)
    application.include_router(weather.router)
    application.include_router(privacy.router)
    return application


app = create_app()
