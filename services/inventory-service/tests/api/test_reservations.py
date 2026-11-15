import asyncio
from threading import Barrier
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.main import app
from app.models import Inventory, InventoryReservation
from app.repositories import inventory_reservation


@pytest.fixture
def setup_api(migrated_engine: Engine):
    inventory_id = uuid4()
    with Session(migrated_engine) as session:
        session.add(Inventory(id=inventory_id, quantity_available=5))
        session.commit()

    def override():
        with Session(migrated_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    yield inventory_id
    app.dependency_overrides.pop(get_session, None)


def request(payload: dict) -> httpx.Response:
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            return await client.post("/reservations", json=payload)

    return asyncio.run(run())


def snapshot(engine: Engine, inventory_id):
    with Session(engine) as session:
        return session.get(Inventory, inventory_id).quantity_available, session.scalar(
            select(func.count()).select_from(InventoryReservation)
        )


def test_http_success_and_conflicts(setup_api, migrated_engine: Engine):
    inventory_id, order_id = setup_api, uuid4()
    payload = {
        "order_id": str(order_id),
        "inventory_id": str(inventory_id),
        "quantity": 3,
    }
    response = request(payload)
    assert response.status_code == 201
    data = response.json()
    assert set(data) == {
        "id",
        "order_id",
        "inventory_id",
        "quantity",
        "status",
        "created_at",
        "updated_at",
    }
    assert data["status"] == "RESERVED" and data["quantity"] == 3
    assert request(payload).status_code == 409
    assert (
        request({**payload, "order_id": str(uuid4()), "quantity": 3}).status_code == 409
    )
    assert request({**payload, "inventory_id": str(uuid4())}).status_code == 404
    assert snapshot(migrated_engine, inventory_id) == (2, 1)


@pytest.mark.parametrize(
    "change",
    [
        {"quantity": 0},
        {"quantity": -1},
        {"quantity": 2147483648},
        {"quantity": None},
        {"quantity": 1.5},
        {"order_id": "bad"},
        {"inventory_id": None},
        {"quantity": "missing"},
    ],
)
def test_invalid(setup_api, migrated_engine: Engine, change: dict):
    payload = {"order_id": str(uuid4()), "inventory_id": str(setup_api), "quantity": 1}
    payload.update(change)
    if change == {"quantity": "missing"}:
        del payload["quantity"]
    assert request(payload).status_code == 422
    assert snapshot(migrated_engine, setup_api) == (5, 0)


def test_unexpected_failure_rolls_back_and_hides_details(
    setup_api, migrated_engine: Engine, monkeypatch
):
    def fail(session, reservation):
        raise RuntimeError("secret SQL details")

    monkeypatch.setattr(inventory_reservation, "add", fail)
    response = request(
        {"order_id": str(uuid4()), "inventory_id": str(setup_api), "quantity": 2}
    )
    assert response.status_code == 500
    assert "secret" not in response.text
    assert snapshot(migrated_engine, setup_api) == (5, 0)


@pytest.mark.parametrize("same_order", [False, True])
def test_concurrent_requests(
    setup_api, migrated_engine: Engine, monkeypatch, same_order: bool
):
    inventory_id = setup_api
    with Session(migrated_engine) as session:
        session.get(Inventory, inventory_id).quantity_available = 5 if same_order else 1
        session.commit()
    barrier = Barrier(2, timeout=5)
    original = app.dependency_overrides[get_session]

    def override():
        with migrated_engine.connect() as connection, Session(connection) as session:
            barrier.wait()
            yield session

    app.dependency_overrides[get_session] = override
    first = str(uuid4())
    payloads = [
        {"order_id": first, "inventory_id": str(inventory_id), "quantity": 1},
        {
            "order_id": first if same_order else str(uuid4()),
            "inventory_id": str(inventory_id),
            "quantity": 1,
        },
    ]

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
            timeout=10,
        ) as client:
            return await asyncio.wait_for(
                asyncio.gather(
                    *(client.post("/reservations", json=p) for p in payloads)
                ),
                timeout=10,
            )

    try:
        responses = asyncio.run(run())
    finally:
        app.dependency_overrides[get_session] = original
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert snapshot(migrated_engine, inventory_id) == (4 if same_order else 0, 1)
