from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.repositories.reservation_repository import SqlAlchemyReservationRepository
from app.services.exceptions import DuplicateReservation


class SqlAlchemyInventoryUnitOfWork:
    def __init__(self, session: Session):
        self.session = session
        self.inventories = SqlAlchemyInventoryRepository(session)
        self.reservations = SqlAlchemyReservationRepository(session)

    @contextmanager
    def begin(self) -> Iterator[None]:
        try:
            with self.session.begin():
                yield
        except IntegrityError as exc:
            original = exc.orig
            if (
                getattr(original, "sqlstate", None) == "23505"
                and getattr(getattr(original, "diag", None), "constraint_name", None)
                == "uq_inventory_reservations_order_inventory"
            ):
                raise DuplicateReservation() from exc
            raise
