import asyncio
from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import get_session
from app.main import app


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def request_health() -> Response:
    async def request() -> Response:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/health")

    return asyncio.run(request())


def test_health_returns_ok_when_database_responds() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    def session_override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    try:
        response = request_health()
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok"}
    finally:
        engine.dispose()


def test_health_returns_503_when_database_fails() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    connection = engine.connect()
    connection.close()

    def session_override() -> Iterator[Session]:
        with Session(bind=connection) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    try:
        response = request_health()
        assert response.status_code == 503
        assert response.json() == {"status": "error", "database": "unavailable"}
    finally:
        engine.dispose()
