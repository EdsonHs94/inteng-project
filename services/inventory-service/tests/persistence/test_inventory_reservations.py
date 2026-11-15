from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from psycopg.errors import (
    CheckViolation,
    ForeignKeyViolation,
    NotNullViolation,
    UniqueViolation,
)
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Inventory, InventoryReservation


@pytest.mark.parametrize("status", ["RESERVED", "RELEASED", "CONFIRMED"])
def test_reservation_persists_and_updates(migrated_engine: Engine, status: str) -> None:
    with Session(migrated_engine) as session:
        inventory = Inventory(quantity_available=10)
        session.add(inventory)
        session.flush()
        inventory_id, order_id = inventory.id, uuid4()
        reservation = InventoryReservation(
            inventory_id=inventory_id, order_id=order_id, quantity=2, status=status
        )
        session.add(reservation)
        session.flush()
        reservation_id = reservation.id
        assert isinstance(reservation_id, UUID)
        created, updated = reservation.created_at, reservation.updated_at
        assert created.tzinfo is not None and updated.tzinfo is not None
        assert (
            created.utcoffset().total_seconds() == 0
            and updated.utcoffset().total_seconds() == 0
        )
        session.commit()
    with Session(migrated_engine) as session:
        stored = session.get(InventoryReservation, reservation_id)
        assert stored is not None
        assert (
            stored.order_id,
            stored.inventory.id,
            stored.quantity,
            stored.status,
        ) == (order_id, inventory_id, 2, status)
        assert stored.inventory.quantity_available == 10
        stored.quantity = 3
        session.commit()
    with Session(migrated_engine) as session:
        stored = session.get(InventoryReservation, reservation_id)
        assert stored is not None
        assert stored.created_at.astimezone(UTC) == created.astimezone(UTC)
        assert stored.updated_at.astimezone(UTC) > updated.astimezone(UTC)
        assert stored.inventory.quantity_available == 10


@pytest.mark.parametrize(
    ("case", "error_type", "diagnostic", "expected"),
    [
        (
            "duplicate-id",
            UniqueViolation,
            "constraint_name",
            "inventory_reservations_pkey",
        ),
        (
            "duplicate-pair",
            UniqueViolation,
            "constraint_name",
            "uq_inventory_reservations_order_inventory",
        ),
        (
            "unknown-inventory",
            ForeignKeyViolation,
            "constraint_name",
            "inventory_reservations_inventory_id_fkey",
        ),
        (
            "zero",
            CheckViolation,
            "constraint_name",
            "ck_inventory_reservations_quantity",
        ),
        (
            "negative",
            CheckViolation,
            "constraint_name",
            "ck_inventory_reservations_quantity",
        ),
        (
            "invalid-status",
            CheckViolation,
            "constraint_name",
            "ck_inventory_reservations_status",
        ),
        *(
            (f"null-{field}", NotNullViolation, "column_name", field)
            for field in (
                "id",
                "order_id",
                "inventory_id",
                "quantity",
                "status",
                "created_at",
                "updated_at",
            )
        ),
        ("omitted-status", NotNullViolation, "column_name", "status"),
    ],
)
def test_reservation_constraints(
    migrated_engine: Engine,
    case: str,
    error_type: type[Exception],
    diagnostic: str,
    expected: str,
) -> None:
    with Session(migrated_engine) as session:
        inventory = Inventory(quantity_available=10)
        session.add(inventory)
        session.flush()
        inventory_id, order_id, reservation_id = inventory.id, uuid4(), uuid4()
        session.add(
            InventoryReservation(
                id=reservation_id,
                order_id=order_id,
                inventory_id=inventory_id,
                quantity=1,
                status="RESERVED",
            )
        )
        session.commit()
        values = dict(
            id=uuid4(),
            order_id=uuid4(),
            inventory_id=inventory_id,
            quantity=1,
            status="CONFIRMED",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        if case == "duplicate-id":
            values["id"] = reservation_id
        elif case == "duplicate-pair":
            values["order_id"] = order_id
        elif case == "unknown-inventory":
            values["inventory_id"] = uuid4()
        elif case in ("zero", "negative"):
            values["quantity"] = 0 if case == "zero" else -1
        elif case == "invalid-status":
            values["status"] = "OTHER"
        elif case.startswith("null-"):
            values[case[5:]] = None
        else:
            del values["status"]
        columns = ", ".join(values)
        binds = ", ".join(f":{key}" for key in values)
        with pytest.raises(IntegrityError) as error:
            session.execute(
                text(
                    f"INSERT INTO inventory_reservations ({columns}) VALUES ({binds})"
                ),
                values,
            )
            session.commit()
        session.rollback()
        assert isinstance(error.value.orig, error_type)
        assert error.value.orig.diag.table_name == "inventory_reservations"
        assert getattr(error.value.orig.diag, diagnostic) == expected
        assert (
            session.scalar(select(func.count()).select_from(InventoryReservation)) == 1
        )


def test_unique_pair_allows_either_component_to_repeat(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        first, second = (
            Inventory(quantity_available=10),
            Inventory(quantity_available=20),
        )
        session.add_all([first, second])
        session.flush()
        order = uuid4()
        session.add_all(
            [
                InventoryReservation(
                    order_id=order, inventory_id=first.id, quantity=1, status="RESERVED"
                ),
                InventoryReservation(
                    order_id=order,
                    inventory_id=second.id,
                    quantity=1,
                    status="RELEASED",
                ),
                InventoryReservation(
                    order_id=uuid4(),
                    inventory_id=first.id,
                    quantity=1,
                    status="CONFIRMED",
                ),
            ]
        )
        session.commit()
        assert (
            session.scalar(select(func.count()).select_from(InventoryReservation)) == 3
        )
