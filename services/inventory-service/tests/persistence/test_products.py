from uuid import UUID, uuid4

import pytest
from psycopg.errors import NotNullViolation, UniqueViolation
from sqlalchemy import Engine, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product


def test_product_survives_commit_and_new_session(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        product = Product(sku="SKU-1", name="Product one")
        session.add(product)
        session.flush()
        product_id = product.id
        assert isinstance(product_id, UUID)
        session.commit()

    with Session(migrated_engine) as session:
        stored = session.get(Product, product_id)
        assert stored is not None
        assert (stored.id, stored.sku, stored.name) == (
            product_id,
            "SKU-1",
            "Product one",
        )


@pytest.mark.parametrize(
    ("case", "expected_error", "diagnostic", "expected_value"),
    [
        ("duplicate-id", UniqueViolation, "constraint_name", "products_pkey"),
        ("duplicate-sku", UniqueViolation, "constraint_name", "products_sku_key"),
        ("null-sku", NotNullViolation, "column_name", "sku"),
        ("null-name", NotNullViolation, "column_name", "name"),
    ],
)
def test_product_constraints(
    migrated_engine: Engine,
    case: str,
    expected_error: type[Exception],
    diagnostic: str,
    expected_value: str,
) -> None:
    existing_id = uuid4()
    with Session(migrated_engine) as session:
        session.add(Product(id=existing_id, sku="SKU-1", name="Existing"))
        session.commit()

        values = {"id": uuid4(), "sku": "SKU-2", "name": "New"}
        if case == "duplicate-id":
            values["id"] = existing_id
        elif case == "duplicate-sku":
            values["sku"] = "SKU-1"
        elif case == "null-sku":
            values["sku"] = None
        else:
            values["name"] = None

        with pytest.raises(IntegrityError) as error:
            session.execute(insert(Product.__table__).values(**values))
            session.commit()
        session.rollback()

        assert isinstance(error.value.orig, expected_error)
        assert error.value.orig.diag.table_name == "products"
        assert getattr(error.value.orig.diag, diagnostic) == expected_value
        assert session.scalar(select(func.count()).select_from(Product)) == 1
