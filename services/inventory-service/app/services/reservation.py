from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InventoryReservation
from app.repositories import inventory, inventory_reservation


class InventoryNotFound(Exception):
    pass


class DuplicateReservation(Exception):
    pass


class InsufficientStock(Exception):
    pass


@dataclass(frozen=True)
class ReservationResult:
    id: UUID
    order_id: UUID
    inventory_id: UUID
    quantity: int
    status: str
    created_at: datetime
    updated_at: datetime


def reserve(
    session: Session, order_id: UUID, inventory_id: UUID, quantity: int
) -> ReservationResult:
    """Own the transaction; repositories only flush within this session."""
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    try:
        with session.begin():
            row = inventory.get_for_update(session, inventory_id)
            if row is None:
                raise InventoryNotFound()
            if inventory_reservation.find_by_pair(session, order_id, inventory_id):
                raise DuplicateReservation()
            if row.quantity_available < quantity:
                raise InsufficientStock()
            inventory.set_quantity(session, row, row.quantity_available - quantity)
            reservation = InventoryReservation(
                order_id=order_id,
                inventory_id=inventory_id,
                quantity=quantity,
                status="RESERVED",
            )
            inventory_reservation.add(session, reservation)
            result = ReservationResult(
                id=reservation.id,
                order_id=reservation.order_id,
                inventory_id=reservation.inventory_id,
                quantity=reservation.quantity,
                status=reservation.status,
                created_at=reservation.created_at,
                updated_at=reservation.updated_at,
            )
        return result
    except IntegrityError as exc:
        original = exc.orig
        if (
            getattr(original, "sqlstate", None) == "23505"
            and getattr(getattr(original, "diag", None), "constraint_name", None)
            == "uq_inventory_reservations_order_inventory"
        ):
            raise DuplicateReservation() from exc
        raise
