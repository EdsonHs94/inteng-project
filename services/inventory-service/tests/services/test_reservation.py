from uuid import UUID, uuid4

import pytest
from psycopg.errors import ForeignKeyViolation
from sqlalchemy import Engine, event, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Inventory, InventoryReservation
from app.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.repositories.reservation_repository import SqlAlchemyReservationRepository
from app.repositories.unit_of_work import SqlAlchemyInventoryUnitOfWork
from app.schemas.reservation import ReservationResponse
from app.services.exceptions import (
    DuplicateReservation,
    InsufficientStock,
    InventoryNotFound,
)
from app.services.reservation_service import ReservationService


def seed(engine: Engine, quantity: int) -> UUID:
    inventory_id = uuid4()
    with Session(engine) as session:
        session.add(Inventory(id=inventory_id, quantity_available=quantity))
        session.commit()
    return inventory_id


def state(engine: Engine, inventory_id: UUID) -> tuple[int, int]:
    with Session(engine) as session:
        return session.get(Inventory, inventory_id).quantity_available, session.scalar(
            select(func.count()).select_from(InventoryReservation)
        )


@pytest.mark.parametrize("quantity", [2, 5])
def test_success(migrated_engine: Engine, quantity: int) -> None:
    inventory_id = seed(migrated_engine, 5)
    with Session(migrated_engine) as session:
        result, created = ReservationService(
            SqlAlchemyInventoryUnitOfWork(session)
        ).reserve(uuid4(), inventory_id, quantity)
    assert created and result.status == "RESERVED"
    assert state(migrated_engine, inventory_id) == (5 - quantity, 1)


@pytest.mark.parametrize("available", [0, 1])
def test_insufficient_rolls_back_provisional_reservation(
    migrated_engine: Engine, available: int
) -> None:
    inventory_id = seed(migrated_engine, available)
    with Session(migrated_engine) as session, pytest.raises(InsufficientStock):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            uuid4(), inventory_id, 2
        )
    assert state(migrated_engine, inventory_id) == (available, 0)


def test_missing_and_mismatched_quantity(migrated_engine: Engine) -> None:
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
    original = SqlAlchemyInventoryRepository.set_quantity

    def fail(self, *args) -> None:
        original(self, *args)
        assert (
            self.session.scalar(
                select(Inventory.quantity_available).where(Inventory.id == inventory_id)
            )
            == 3
        )
        assert (
            self.session.scalar(select(func.count()).select_from(InventoryReservation))
            == 1
        )
        raise RuntimeError("controlled failure")

    monkeypatch.setattr(SqlAlchemyInventoryRepository, "set_quantity", fail)
    with Session(migrated_engine) as session, pytest.raises(RuntimeError):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            uuid4(), inventory_id, 2
        )
    assert state(migrated_engine, inventory_id) == (5, 0)


def test_other_integrity_error_is_not_duplicate(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory_id = seed(migrated_engine, 5)
    original = SqlAlchemyReservationRepository.try_create_reservation

    def invalid(self, order_id, inventory_id, quantity, status):
        return original(self, order_id, inventory_id, 0, status)

    monkeypatch.setattr(
        SqlAlchemyReservationRepository, "try_create_reservation", invalid
    )
    with Session(migrated_engine) as session, pytest.raises(IntegrityError) as error:
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            uuid4(), inventory_id, 2
        )
    assert error.value.orig.diag.constraint_name == "ck_inventory_reservations_quantity"
    assert state(migrated_engine, inventory_id) == (5, 0)


@pytest.mark.parametrize("status", ["RELEASED", "CONFIRMED"])
def test_existing_other_status_is_conflict(
    migrated_engine: Engine, status: str
) -> None:
    inventory_id, order_id = seed(migrated_engine, 0), uuid4()
    with Session(migrated_engine) as session:
        session.add(
            InventoryReservation(
                order_id=order_id, inventory_id=inventory_id, quantity=1, status=status
            )
        )
        session.commit()
    with Session(migrated_engine) as session, pytest.raises(DuplicateReservation):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            order_id, inventory_id, 1
        )
    assert state(migrated_engine, inventory_id) == (0, 1)


def test_deferred_failure_at_commit_rolls_back(migrated_engine: Engine) -> None:
    inventory_id = seed(migrated_engine, 5)
    # Test-only deferred FK: keep the production business UNIQUE immediate.
    with migrated_engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE inventory_reservations ADD CONSTRAINT test_deferred_order_fk "
            "FOREIGN KEY (order_id) REFERENCES products (id) "
            "DEFERRABLE INITIALLY DEFERRED"
        )
    with Session(migrated_engine) as session:
        with pytest.raises(IntegrityError) as error:
            ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
                uuid4(), inventory_id, 2
            )
        assert not session.in_transaction()
        assert (
            session.scalar(select(func.count()).select_from(InventoryReservation)) == 0
        )
    assert isinstance(error.value.orig, ForeignKeyViolation)
    assert error.value.orig.diag.constraint_name == "test_deferred_order_fk"
    assert state(migrated_engine, inventory_id) == (5, 0)


def test_result_serializes_after_commit_without_queries(
    migrated_engine: Engine,
) -> None:
    inventory_id, order_id = seed(migrated_engine, 5), uuid4()
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(migrated_engine, "before_cursor_execute", capture)
    try:
        for expected_created in (True, False):
            with Session(migrated_engine) as session:
                result, created = ReservationService(
                    SqlAlchemyInventoryUnitOfWork(session)
                ).reserve(order_id, inventory_id, 2)
                assert isinstance(result, ReservationResponse)
                assert created is expected_created
                count = len(statements)
                response = result.model_dump(mode="json")
                assert len(statements) == count
            assert response["status"] == "RESERVED" and response["quantity"] == 2
    finally:
        event.remove(migrated_engine, "before_cursor_execute", capture)
    assert state(migrated_engine, inventory_id) == (3, 1)


def test_result_validation_error_rolls_back_insert(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory_id = seed(migrated_engine, 5)

    def fail(cls, row, **kwargs):
        session = inspect(row).session
        assert (
            session.scalar(select(func.count()).select_from(InventoryReservation)) == 1
        )
        raise ValueError("invalid response")

    monkeypatch.setattr(ReservationResponse, "model_validate", classmethod(fail))
    with (
        Session(migrated_engine) as session,
        pytest.raises(ValueError, match="invalid response"),
    ):
        ReservationService(SqlAlchemyInventoryUnitOfWork(session)).reserve(
            uuid4(), inventory_id, 2
        )
    assert state(migrated_engine, inventory_id) == (5, 0)
