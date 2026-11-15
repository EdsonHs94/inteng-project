from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


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


class ReservationUnitOfWork(Protocol):
    def begin(self) -> AbstractContextManager[None]: ...
    def get_quantity_for_update(self, inventory_id: UUID) -> int | None: ...
    def has_reservation(self, order_id: UUID, inventory_id: UUID) -> bool: ...
    def set_quantity(self, inventory_id: UUID, quantity: int) -> None: ...
    def create_reservation(
        self, order_id: UUID, inventory_id: UUID, quantity: int, status: str
    ) -> ReservationResult: ...


def reserve(
    uow: ReservationUnitOfWork, order_id: UUID, inventory_id: UUID, quantity: int
) -> ReservationResult:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    with uow.begin():
        available = uow.get_quantity_for_update(inventory_id)
        if available is None:
            raise InventoryNotFound()
        if uow.has_reservation(order_id, inventory_id):
            raise DuplicateReservation()
        if available < quantity:
            raise InsufficientStock()
        uow.set_quantity(inventory_id, available - quantity)
        result = uow.create_reservation(order_id, inventory_id, quantity, "RESERVED")
    return result
