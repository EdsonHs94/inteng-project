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
from app.repositories.reservation_repository import SqlAlchemyReservationRepository


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
    replay = request(payload)
    assert replay.status_code == 200
    assert replay.json() == data
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
    def fail(self, *args):
        raise RuntimeError("secret SQL details")

    monkeypatch.setattr(SqlAlchemyReservationRepository, "try_create_reservation", fail)
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
    assert sorted(r.status_code for r in responses) == (
        [200, 201] if same_order else [201, 409]
    )
    if same_order:
        assert responses[0].json() == responses[1].json()
    assert snapshot(migrated_engine, inventory_id) == (4 if same_order else 0, 1)


def test_service_dependency_can_be_replaced():
    from datetime import UTC, datetime

    from app.api.dependencies import get_reservation_service
    from app.schemas.reservation import ReservationResponse

    inventory_id, order_id = uuid4(), uuid4()

    class StubService:
        def reserve(self, order, inventory, quantity):
            return ReservationResponse(
                id=uuid4(),
                order_id=order,
                inventory_id=inventory,
                quantity=quantity,
                status="RESERVED",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ), True

    app.dependency_overrides[get_reservation_service] = lambda: StubService()
    try:
        response = request(
            {
                "order_id": str(order_id),
                "inventory_id": str(inventory_id),
                "quantity": 2,
            }
        )
        assert response.status_code == 201 and response.json()["quantity"] == 2
    finally:
        app.dependency_overrides.pop(get_reservation_service, None)


@pytest.mark.parametrize("quantity", [3, 5])
def test_repeated_identical_requests_preserve_original(
    setup_api, migrated_engine: Engine, quantity: int
):
    payload = {
        "order_id": str(uuid4()),
        "inventory_id": str(setup_api),
        "quantity": quantity,
    }
    initial = request(payload)
    assert initial.status_code == 201
    for _ in range(3):
        replay = request(payload)
        assert replay.status_code == 200
        assert replay.json() == initial.json()
        assert snapshot(migrated_engine, setup_api) == (5 - quantity, 1)
    with Session(migrated_engine) as session:
        row = session.scalar(select(InventoryReservation))
        assert str(row.id) == initial.json()["id"]
        assert row.quantity == quantity and row.status == "RESERVED"


@pytest.mark.parametrize("quantity", [1, 4])
def test_changed_quantity_is_conflict_even_when_stock_is_zero(
    setup_api, migrated_engine: Engine, quantity: int
):
    payload = {
        "order_id": str(uuid4()),
        "inventory_id": str(setup_api),
        "quantity": 5,
    }
    initial = request(payload)
    assert initial.status_code == 201
    assert request({**payload, "quantity": quantity}).status_code == 409
    replay = request(payload)
    assert replay.status_code == 200 and replay.json() == initial.json()
    assert snapshot(migrated_engine, setup_api) == (0, 1)


@pytest.mark.parametrize("reservation_status", ["RELEASED", "CONFIRMED"])
@pytest.mark.parametrize("quantity", [2, 3])
def test_other_status_is_never_reactivated(
    setup_api, migrated_engine: Engine, reservation_status: str, quantity: int
):
    from app.schemas.reservation import ReservationResponse

    order_id = uuid4()
    with Session(migrated_engine) as session:
        session.get(Inventory, setup_api).quantity_available = 0
        row = InventoryReservation(
            order_id=order_id,
            inventory_id=setup_api,
            quantity=2,
            status=reservation_status,
        )
        session.add(row)
        session.flush()
        original = ReservationResponse.model_validate(row, from_attributes=True)
        session.commit()
    assert (
        request(
            {
                "order_id": str(order_id),
                "inventory_id": str(setup_api),
                "quantity": quantity,
            }
        ).status_code
        == 409
    )
    with Session(migrated_engine) as session:
        row = session.get(InventoryReservation, original.id)
        assert ReservationResponse.model_validate(row, from_attributes=True) == original
    assert snapshot(migrated_engine, setup_api) == (0, 1)


def test_openapi_documents_creation_and_replay():
    responses = app.openapi()["paths"]["/reservations"]["post"]["responses"]
    assert (
        responses["200"]["content"]["application/json"]["schema"]
        == responses["201"]["content"]["application/json"]["schema"]
    )
