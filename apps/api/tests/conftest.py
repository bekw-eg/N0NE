from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import ROOT, Settings
from app.main import create_app
from app.repositories.poi_repository import POIRepository


@pytest.fixture(scope="session")
def repository() -> POIRepository:
    return POIRepository.load(ROOT / "data/astana/pois.json")


@pytest.fixture
def client(repository: POIRepository) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(cors_origins=[]), repository)) as active:
        yield active
