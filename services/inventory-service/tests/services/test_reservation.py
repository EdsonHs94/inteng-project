from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.models import Inventory, InventoryReservation
from app.repositories import inventory_reservation
from app.services.reservation import (
    DuplicateReservation,
    InsufficientStock,
    InventoryNotFound,
    reserve,
)


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
        result = reserve(session, uuid4(), inventory_id, quantity)
    assert result.status == "RESERVED"
    assert state(migrated_engine, inventory_id) == (5 - quantity, 1)


@pytest.mark.parametrize("available", [0, 1])
def test_insufficient(migrated_engine: Engine, available: int) -> None:
    inventory_id = seed(migrated_engine, available)
    with Session(migrated_engine) as session, pytest.raises(InsufficientStock):
        reserve(session, uuid4(), inventory_id, 2)
    assert state(migrated_engine, inventory_id) == (available, 0)


def test_missing_and_duplicate(migrated_engine: Engine) -> None:
    inventory_id, order_id = seed(migrated_engine, 5), uuid4()
    with Session(migrated_engine) as session, pytest.raises(InventoryNotFound):
        reserve(session, order_id, uuid4(), 1)
    with Session(migrated_engine) as session:
        reserve(session, order_id, inventory_id, 2)
    with Session(migrated_engine) as session, pytest.raises(DuplicateReservation):
        reserve(session, order_id, inventory_id, 1)
    assert state(migrated_engine, inventory_id) == (3, 1)


def test_failure_after_flushed_discount_rolls_back(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory_id = seed(migrated_engine, 5)

    def fail(session: Session, reservation: InventoryReservation) -> None:
        assert (
            session.scalar(
                select(Inventory.quantity_available).where(Inventory.id == inventory_id)
            )
            == 3
        )
        raise RuntimeError("controlled failure")

    monkeypatch.setattr(inventory_reservation, "add", fail)
    with Session(migrated_engine) as session, pytest.raises(RuntimeError):
        reserve(session, uuid4(), inventory_id, 2)
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
    monkeypatch.setattr(inventory_reservation, "find_by_pair", lambda *args: None)
    with Session(migrated_engine) as session, pytest.raises(DuplicateReservation):
        reserve(session, order_id, inventory_id, 2)
    assert state(migrated_engine, inventory_id) == (5, 1)


def test_other_integrity_error_is_not_duplicate(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.exc import IntegrityError

    inventory_id = seed(migrated_engine, 5)
    original = inventory_reservation.add

    def invalid(session, reservation):
        reservation.quantity = 0
        original(session, reservation)

    monkeypatch.setattr(inventory_reservation, "add", invalid)
    with Session(migrated_engine) as session, pytest.raises(IntegrityError):
        reserve(session, uuid4(), inventory_id, 2)
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
        reserve(session, order_id, inventory_id, 2)
    assert state(migrated_engine, inventory_id) == (5, 1)
