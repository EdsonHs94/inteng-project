from datetime import UTC
from uuid import UUID, uuid4

import pytest
from psycopg.errors import CheckViolation, ForeignKeyViolation
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Inventory, InventoryReservation
from app.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.repositories.reservation_repository import SqlAlchemyReservationRepository


def test_repositories_share_caller_transaction(migrated_engine: Engine) -> None:
    inventory_id, order_id = uuid4(), uuid4()
    with Session(migrated_engine) as session:
        session.add(Inventory(id=inventory_id, quantity_available=5))
        session.commit()
    with Session(migrated_engine) as session:
        inventories = SqlAlchemyInventoryRepository(session)
        reservations = SqlAlchemyReservationRepository(session)
        assert inventories.get_quantity_for_update(uuid4()) is None
        assert inventories.get_quantity_for_update(inventory_id) == 5
        assert reservations.get_by_pair(order_id, inventory_id) is None
        inventories.set_quantity(inventory_id, 2)
        reservation = reservations.try_create_reservation(
            order_id, inventory_id, 3, "RESERVED"
        )
        assert reservation.id is not None
        assert reservations.get_by_pair(order_id, inventory_id) is not None
        session.rollback()
    with Session(migrated_engine) as session:
        assert session.get(Inventory, inventory_id).quantity_available == 5
        assert (
            SqlAlchemyReservationRepository(session).get_by_pair(order_id, inventory_id)
            is None
        )


def test_conditional_insert_preserves_existing_reservation(migrated_engine: Engine):
    inventory_id, order_id = uuid4(), uuid4()
    with Session(migrated_engine) as session:
        session.add(Inventory(id=inventory_id, quantity_available=5))
        session.commit()
        repository = SqlAlchemyReservationRepository(session)
        assert repository.get_by_pair(order_id, inventory_id) is None
        created = repository.try_create_reservation(
            order_id, inventory_id, 2, "RESERVED"
        )
        assert created is not None
        assert isinstance(created.id, UUID)
        assert created.created_at.utcoffset() == UTC.utcoffset(created.created_at)
        assert created.updated_at.utcoffset() == UTC.utcoffset(created.updated_at)
        session.commit()

    with Session(migrated_engine) as session:
        repository = SqlAlchemyReservationRepository(session)
        assert (
            repository.try_create_reservation(order_id, inventory_id, 4, "CONFIRMED")
            is None
        )
        assert repository.get_by_pair(order_id, inventory_id) == created
        session.commit()

    with Session(migrated_engine) as session:
        assert (
            SqlAlchemyReservationRepository(session).get_by_pair(order_id, inventory_id)
            == created
        )
        assert (
            session.scalar(select(func.count()).select_from(InventoryReservation)) == 1
        )
        assert session.get(Inventory, inventory_id).quantity_available == 5


def test_conditional_insert_is_rolled_back_by_caller(migrated_engine: Engine):
    inventory_id, order_id = uuid4(), uuid4()
    with Session(migrated_engine) as session:
        session.add(Inventory(id=inventory_id, quantity_available=5))
        session.commit()
        repository = SqlAlchemyReservationRepository(session)
        assert repository.try_create_reservation(order_id, inventory_id, 1, "RESERVED")
        session.rollback()
    with Session(migrated_engine) as session:
        assert (
            SqlAlchemyReservationRepository(session).get_by_pair(order_id, inventory_id)
            is None
        )


@pytest.mark.parametrize(
    ("quantity", "status", "missing_inventory", "error_type", "constraint"),
    [
        (0, "RESERVED", False, CheckViolation, "ck_inventory_reservations_quantity"),
        (1, "INVALID", False, CheckViolation, "ck_inventory_reservations_status"),
        (
            1,
            "RESERVED",
            True,
            ForeignKeyViolation,
            "inventory_reservations_inventory_id_fkey",
        ),
    ],
)
def test_conditional_insert_does_not_hide_other_constraints(
    migrated_engine: Engine, quantity, status, missing_inventory, error_type, constraint
):
    inventory_id = uuid4()
    with Session(migrated_engine) as session:
        if not missing_inventory:
            session.add(Inventory(id=inventory_id, quantity_available=5))
            session.commit()
        with pytest.raises(IntegrityError) as error:
            SqlAlchemyReservationRepository(session).try_create_reservation(
                uuid4(), inventory_id, quantity, status
            )
        session.rollback()
        assert isinstance(error.value.orig, error_type)
        assert error.value.orig.diag.constraint_name == constraint
        assert (
            session.scalar(select(func.count()).select_from(InventoryReservation)) == 0
        )
