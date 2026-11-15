from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Inventory


class SqlAlchemyInventoryRepository:
    def __init__(self, session: Session):
        self.session = session
        self._locked_inventory: Inventory | None = None

    def get_quantity_for_update(self, inventory_id: UUID) -> int | None:
        self._locked_inventory = self.session.scalar(
            select(Inventory).where(Inventory.id == inventory_id).with_for_update()
        )
        return (
            self._locked_inventory.quantity_available
            if self._locked_inventory is not None
            else None
        )

    def set_quantity(self, inventory_id: UUID, quantity: int) -> None:
        if self._locked_inventory is None or self._locked_inventory.id != inventory_id:
            raise ValueError("inventory must be locked before update")
        self._locked_inventory.quantity_available = quantity
        self.session.flush()
