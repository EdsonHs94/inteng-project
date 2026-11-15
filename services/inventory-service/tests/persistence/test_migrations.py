import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from app.models import Base


def test_migration_uses_settings_connection(
    postgres_engine: Engine, alembic_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POSTGRES_DB", postgres_engine.url.database)
    command.upgrade(alembic_config, "head")
    command.check(alembic_config)
    with postgres_engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        )


def test_initial_migration_is_reversible(
    postgres_engine: Engine, alembic_config: Config
) -> None:
    with postgres_engine.begin() as connection:
        connection.execute(text("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)"))

    for action, revision in (
        (command.upgrade, "head"),
        (command.downgrade, "base"),
        (command.upgrade, "head"),
    ):
        with postgres_engine.begin() as connection:
            alembic_config.attributes["connection"] = connection
            action(alembic_config, revision)

        tables = set(inspect(postgres_engine).get_table_names())
        assert "unrelated" in tables
        if revision == "base":
            assert "products" not in tables
            assert "inventories" not in tables
        else:
            assert {"products", "inventories"} <= tables
            with postgres_engine.connect() as connection:
                context = MigrationContext.configure(
                    connection,
                    opts={
                        "include_object": lambda obj, name, kind, reflected, compare: (
                            name != "unrelated"
                        )
                    },
                )
                assert compare_metadata(context, Base.metadata) == []
            checks = inspect(postgres_engine).get_check_constraints("inventories")
            assert any(
                check["name"] == "ck_inventories_quantity_available"
                and "quantity_available >= 0" in check["sqltext"]
                for check in checks
            )


def test_reservation_migration_preserves_existing_data(
    postgres_engine: Engine, alembic_config: Config
) -> None:
    from uuid import uuid4

    product_id, inventory_id = uuid4(), uuid4()
    with postgres_engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "0001")
        connection.execute(
            text("INSERT INTO products (id, sku, name) VALUES (:id, 'sku', 'name')"),
            {"id": product_id},
        )
        connection.execute(
            text(
                "INSERT INTO inventories (id, product_id, quantity_available) "
                "VALUES (:id, :product, 7)"
            ),
            {"id": inventory_id, "product": product_id},
        )

    for action, revision in (
        (command.upgrade, "head"),
        (command.downgrade, "0001"),
        (command.upgrade, "head"),
    ):
        with postgres_engine.begin() as connection:
            alembic_config.attributes["connection"] = connection
            action(alembic_config, revision)
            assert connection.execute(
                text("SELECT sku, name FROM products WHERE id = :id"),
                {"id": product_id},
            ).one() == ("sku", "name")
            assert connection.execute(
                text(
                    "SELECT product_id, quantity_available FROM inventories "
                    "WHERE id = :id"
                ),
                {"id": inventory_id},
            ).one() == (product_id, 7)
        inspector = inspect(postgres_engine)
        assert inspector.has_table("inventory_reservations") == (revision == "head")
        if revision == "head":
            assert {
                c["name"]
                for c in inspector.get_check_constraints("inventory_reservations")
            } == {
                "ck_inventory_reservations_quantity",
                "ck_inventory_reservations_status",
            }
            assert inspector.get_unique_constraints("inventory_reservations")[0][
                "column_names"
            ] == ["order_id", "inventory_id"]
            assert (
                inspector.get_foreign_keys("inventory_reservations")[0][
                    "referred_table"
                ]
                == "inventories"
            )
            with postgres_engine.connect() as connection:
                assert (
                    compare_metadata(
                        MigrationContext.configure(connection), Base.metadata
                    )
                    == []
                )
