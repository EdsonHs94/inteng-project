from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Inventory, InventoryReservation
from app.repositories import inventory, inventory_reservation
from app.services.reservation import DuplicateReservation, ReservationResult


class SqlAlchemyReservationUnitOfWork:
    def __init__(self, session: Session):
        self.session = session
        self._locked_inventory: Inventory | None = None

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
        finally:
            self._locked_inventory = None

    def get_quantity_for_update(self, inventory_id: UUID) -> int | None:
        self._locked_inventory = inventory.get_for_update(self.session, inventory_id)
        return (
            self._locked_inventory.quantity_available
            if self._locked_inventory is not None
            else None
        )

    def has_reservation(self, order_id: UUID, inventory_id: UUID) -> bool:
        return (
            inventory_reservation.find_by_pair(self.session, order_id, inventory_id)
            is not None
        )

    def set_quantity(self, inventory_id: UUID, quantity: int) -> None:
        if self._locked_inventory is None or self._locked_inventory.id != inventory_id:
            raise ValueError("inventory must be locked before update")
        inventory.set_quantity(self.session, self._locked_inventory, quantity)

    def create_reservation(
        self, order_id: UUID, inventory_id: UUID, quantity: int, status: str
    ) -> ReservationResult:
        row = InventoryReservation(
            order_id=order_id,
            inventory_id=inventory_id,
            quantity=quantity,
            status=status,
        )
        inventory_reservation.add(self.session, row)
        return ReservationResult(
            id=row.id,
            order_id=row.order_id,
            inventory_id=row.inventory_id,
            quantity=row.quantity,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
