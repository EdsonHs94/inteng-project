from uuid import UUID, uuid4

import pytest
from psycopg.errors import (
    CheckViolation,
    ForeignKeyViolation,
    NotNullViolation,
    UniqueViolation,
)
from sqlalchemy import Engine, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Inventory, Product


@pytest.mark.parametrize("quantity", [0, 7])
def test_inventory_survives_commit_and_new_session(
    migrated_engine: Engine, quantity: int
) -> None:
    with Session(migrated_engine) as session:
        product = Product(sku="SKU-1", name="Product one")
        session.add(product)
        session.flush()
        product_id = product.id
        inventory = Inventory(product_id=product_id, quantity_available=quantity)
        session.add(inventory)
        session.flush()
        inventory_id = inventory.id
        assert isinstance(inventory_id, UUID)
        session.commit()

    with Session(migrated_engine) as session:
        stored = session.get(Inventory, inventory_id)
        assert stored is not None
        assert (stored.id, stored.product_id, stored.quantity_available) == (
            inventory_id,
            product_id,
            quantity,
        )


def test_inventory_accepts_null_product(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        inventory = Inventory(product_id=None, quantity_available=0)
        session.add(inventory)
        session.flush()
        inventory_id = inventory.id
        session.commit()

    with Session(migrated_engine) as session:
        stored = session.get(Inventory, inventory_id)
        assert stored is not None
        assert stored.product_id is None
        assert stored.quantity_available == 0


@pytest.mark.parametrize(
    ("case", "expected_error", "diagnostic", "expected_value"),
    [
        ("duplicate-id", UniqueViolation, "constraint_name", "inventories_pkey"),
        (
            "unknown-product",
            ForeignKeyViolation,
            "constraint_name",
            "inventories_product_id_fkey",
        ),
        (
            "duplicate-product",
            UniqueViolation,
            "constraint_name",
            "inventories_product_id_key",
        ),
        (
            "negative-quantity",
            CheckViolation,
            "constraint_name",
            "ck_inventories_quantity_available",
        ),
        ("null-quantity", NotNullViolation, "column_name", "quantity_available"),
    ],
)
def test_inventory_constraints(
    migrated_engine: Engine,
    case: str,
    expected_error: type[Exception],
    diagnostic: str,
    expected_value: str,
) -> None:
    existing_id = uuid4()
    product_id = uuid4()
    with Session(migrated_engine) as session:
        session.add(Product(id=product_id, sku="SKU-1", name="Existing"))
        session.flush()
        session.add(
            Inventory(id=existing_id, product_id=product_id, quantity_available=3)
        )
        session.commit()

        values = {"id": uuid4(), "product_id": None, "quantity_available": 1}
        if case == "duplicate-id":
            values["id"] = existing_id
        elif case == "unknown-product":
            values["product_id"] = uuid4()
        elif case == "duplicate-product":
            values["product_id"] = product_id
        elif case == "negative-quantity":
            values["quantity_available"] = -1
        else:
            values["quantity_available"] = None

        with pytest.raises(IntegrityError) as error:
            session.execute(insert(Inventory.__table__).values(**values))
            session.commit()
        session.rollback()

        assert isinstance(error.value.orig, expected_error)
        assert error.value.orig.diag.table_name == "inventories"
        assert getattr(error.value.orig.diag, diagnostic) == expected_value
        assert session.scalar(select(func.count()).select_from(Inventory)) == 1
