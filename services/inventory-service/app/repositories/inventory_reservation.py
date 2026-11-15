from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InventoryReservation


def find_by_pair(
    session: Session, order_id: UUID, inventory_id: UUID
) -> InventoryReservation | None:
    return session.scalar(
        select(InventoryReservation).where(
            InventoryReservation.order_id == order_id,
            InventoryReservation.inventory_id == inventory_id,
        )
    )


def add(session: Session, reservation: InventoryReservation) -> None:
    session.add(reservation)
    session.flush()
