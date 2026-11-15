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
    ) -> ReservationResponse:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        with self.uow.begin():
            available = self.uow.inventories.get_quantity_for_update(inventory_id)
            if available is None:
                raise InventoryNotFound()
            if self.uow.reservations.has_reservation(order_id, inventory_id):
                raise DuplicateReservation()
            if available < quantity:
                raise InsufficientStock()
            self.uow.inventories.set_quantity(inventory_id, available - quantity)
            result = self.uow.reservations.create_reservation(
                order_id, inventory_id, quantity, "RESERVED"
            )
        return result
