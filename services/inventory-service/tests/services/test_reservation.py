from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.models import Inventory, InventoryReservation
from app.repositories.reservation_repository import SqlAlchemyReservationRepository
from app.repositories.unit_of_work import SqlAlchemyInventoryUnitOfWork
from app.services.exceptions import (
    DuplicateReservation,
    InsufficientStock,
    InventoryNotFound,
)
from app.services.reservation_service import ReservationService


def seed(engine: Engine, quantity: int) -> object:
    inventory_id = uuid4()
    with Session(engine) as session:
        session.add(Inventory(id=inventory_id, quantity_available=quantity))
        session.commit()
    return inventory_id


def state(engine: Engine, inventory_id: object) -> tuple[int, int]:
    with Session(engine) as session:
        return session.get(Inventory, inventory_id).quantity_available, session.scalar(
            select(func.count()).select_from(InventoryReservation)
        )


@pytest.mark.parametrize("quantity", [2, 5])
def test_success(migrated_engine: Engine, quantity: int) -> None:
    inventory_id = seed(migrated_engine, 5)
    with Session(migrated_engine) as session:
        result = ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            uuid4(), inventory_id, quantity
        )
    assert result.status == "RESERVED"
    assert state(migrated_engine, inventory_id) == (5 - quantity, 1)


@pytest.mark.parametrize("available", [0, 1])
def test_insufficient(migrated_engine: Engine, available: int) -> None:
    inventory_id = seed(migrated_engine, available)
    with Session(migrated_engine) as session, pytest.raises(InsufficientStock):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            uuid4(), inventory_id, 2
        )
    assert state(migrated_engine, inventory_id) == (available, 0)


def test_missing_and_duplicate(migrated_engine: Engine) -> None:
    inventory_id, order_id = seed(migrated_engine, 5), uuid4()
    with Session(migrated_engine) as session, pytest.raises(InventoryNotFound):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            order_id, uuid4(), 1
        )
    with Session(migrated_engine) as session:
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            order_id, inventory_id, 2
        )
    with Session(migrated_engine) as session, pytest.raises(DuplicateReservation):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            order_id, inventory_id, 1
        )
    assert state(migrated_engine, inventory_id) == (3, 1)


def test_failure_after_flushed_discount_rolls_back(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory_id = seed(migrated_engine, 5)

    def fail(self, *args) -> None:
        session = self.session
        assert (
            session.scalar(
                select(Inventory.quantity_available).where(Inventory.id == inventory_id)
            )
            == 3
        )
        raise RuntimeError("controlled failure")

    monkeypatch.setattr(SqlAlchemyReservationRepository, "create_reservation", fail)
    with Session(migrated_engine) as session, pytest.raises(RuntimeError):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            uuid4(), inventory_id, 2
        )
    assert state(migrated_engine, inventory_id) == (5, 0)


def test_unique_violation_translated_after_rollback(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory_id, order_id = seed(migrated_engine, 5), uuid4()
    with Session(migrated_engine) as session:
        session.add(
            InventoryReservation(
                order_id=order_id,
                inventory_id=inventory_id,
                quantity=1,
                status="RELEASED",
            )
        )
        session.commit()
    monkeypatch.setattr(
        SqlAlchemyReservationRepository, "has_reservation", lambda *args: False
    )
    with Session(migrated_engine) as session, pytest.raises(DuplicateReservation):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            order_id, inventory_id, 2
        )
    assert state(migrated_engine, inventory_id) == (5, 1)


def test_other_integrity_error_is_not_duplicate(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.exc import IntegrityError

    inventory_id = seed(migrated_engine, 5)
    original = SqlAlchemyReservationRepository.create_reservation

    def invalid(self, order_id, inventory_id, quantity, status):
        original(self, order_id, inventory_id, 0, status)

    monkeypatch.setattr(SqlAlchemyReservationRepository, "create_reservation", invalid)
    with Session(migrated_engine) as session, pytest.raises(IntegrityError):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            uuid4(), inventory_id, 2
        )
    assert state(migrated_engine, inventory_id) == (5, 0)


def test_existing_other_status_is_duplicate(migrated_engine: Engine) -> None:
    inventory_id, order_id = seed(migrated_engine, 5), uuid4()
    with Session(migrated_engine) as session:
        session.add(
            InventoryReservation(
                order_id=order_id,
                inventory_id=inventory_id,
                quantity=1,
                status="CONFIRMED",
            )
        )
        session.commit()
    with Session(migrated_engine) as session, pytest.raises(DuplicateReservation):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            order_id, inventory_id, 2
        )
    assert state(migrated_engine, inventory_id) == (5, 1)


def test_deferred_unique_violation_at_commit_rolls_back(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory_id, order_id = seed(migrated_engine, 5), uuid4()
    with migrated_engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE inventory_reservations DROP CONSTRAINT "
            "uq_inventory_reservations_order_inventory"
        )
        connection.exec_driver_sql(
            "ALTER TABLE inventory_reservations ADD CONSTRAINT "
            "uq_inventory_reservations_order_inventory "
            "UNIQUE (order_id, inventory_id) DEFERRABLE INITIALLY DEFERRED"
        )
    with Session(migrated_engine) as session:
        session.add(
            InventoryReservation(
                order_id=order_id,
                inventory_id=inventory_id,
                quantity=1,
                status="RELEASED",
            )
        )
        session.commit()
    monkeypatch.setattr(
        SqlAlchemyReservationRepository, "has_reservation", lambda *args: False
    )
    with Session(migrated_engine) as session, pytest.raises(DuplicateReservation):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            order_id, inventory_id, 2
        )
    assert state(migrated_engine, inventory_id) == (5, 1)


def test_result_serializes_after_commit_without_queries(
    migrated_engine: Engine,
) -> None:
    from sqlalchemy import event

    from app.schemas.reservation import ReservationResponse

    inventory_id = seed(migrated_engine, 5)
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(migrated_engine, "before_cursor_execute", capture)
    try:
        with Session(migrated_engine) as session:
            result = ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
                uuid4(), inventory_id, 2
            )
            count = len(statements)
            response = ReservationResponse.model_validate(result, from_attributes=True)
            assert len(statements) == count
        assert response.status == "RESERVED" and response.quantity == 2
    finally:
        event.remove(migrated_engine, "before_cursor_execute", capture)
