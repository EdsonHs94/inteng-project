from uuid import UUID

from app.schemas.reservation import ReservationResponse
from app.services.contracts import InventoryUnitOfWork
from app.services.exceptions import (
    DuplicateReservation,
    InsufficientStock,
    InventoryNotFound,
)


class ReservationService:
    def __init__(self, uow: InventoryUnitOfWork):
        self.uow = uow

    def reserve(
        self, order_id: UUID, inventory_id: UUID, quantity: int
    ) -> tuple[ReservationResponse, bool]:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        with self.uow.begin():
            available = self.uow.inventories.get_quantity_for_update(inventory_id)
            if available is None:
                raise InventoryNotFound()
            result = self.uow.reservations.try_create_reservation(
                order_id, inventory_id, quantity, "RESERVED"
            )
            if result is None:
                existing = self.uow.reservations.get_by_pair(order_id, inventory_id)
                if existing is None:
                    raise RuntimeError("Conflicting reservation could not be retrieved")
                if existing.quantity != quantity or existing.status != "RESERVED":
                    raise DuplicateReservation()
                return existing, False
            if available < quantity:
                raise InsufficientStock()
            self.uow.inventories.set_quantity(inventory_id, available - quantity)
        return result, True
