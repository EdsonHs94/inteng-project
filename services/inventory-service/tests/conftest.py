from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings

SERVICE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def alembic_config() -> Config:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    return config


@pytest.fixture
def postgres_engine() -> Iterator[Engine]:
    settings = Settings()
    database_name = f"inventory_test_{uuid4().hex}"
    if database_name == settings.postgres_db or not database_name.startswith(
        "inventory_test_"
    ):
        raise ValueError("Persistence tests require a dedicated test database")

    admin_engine = create_engine(
        settings.database_url,
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
        connect_args={"connect_timeout": 3},
    )
    quoted_name = admin_engine.dialect.identifier_preparer.quote(database_name)
    test_engine = create_engine(
        settings.database_url.set(database=database_name),
        poolclass=NullPool,
        connect_args={"connect_timeout": 3},
    )
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
        try:
            yield test_engine
        finally:
            test_engine.dispose()
            with admin_engine.connect() as connection:
                connection.exec_driver_sql(f"DROP DATABASE {quoted_name}")
    finally:
        admin_engine.dispose()


@pytest.fixture
def migrated_engine(postgres_engine: Engine, alembic_config: Config) -> Engine:
    with postgres_engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")
    return postgres_engine
