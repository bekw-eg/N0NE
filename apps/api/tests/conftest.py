from collections.abc import Iterator
from typing import NoReturn

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import ROOT, Settings
from app.main import create_app
from app.repositories.poi_repository import POIRepository


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(transport: httpx.HTTPTransport, request: httpx.Request) -> NoReturn:
        raise AssertionError("Tests must use mock clients, never a real network")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


@pytest.fixture(scope="session")
def repository() -> POIRepository:
    return POIRepository.load(ROOT / "data/astana/pois.json")


@pytest.fixture
def client(repository: POIRepository) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(cors_origins=[]), repository)) as active:
        yield active
