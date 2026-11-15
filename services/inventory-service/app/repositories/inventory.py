from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Inventory


def get_for_update(session: Session, inventory_id: UUID) -> Inventory | None:
    return session.scalar(
        select(Inventory).where(Inventory.id == inventory_id).with_for_update()
    )


def set_quantity(session: Session, inventory: Inventory, quantity: int) -> None:
    inventory.quantity_available = quantity
    session.flush()
