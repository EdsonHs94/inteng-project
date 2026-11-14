from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings

engine = create_engine(
    Settings().database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
