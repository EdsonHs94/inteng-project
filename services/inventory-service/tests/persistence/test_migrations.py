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
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
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
