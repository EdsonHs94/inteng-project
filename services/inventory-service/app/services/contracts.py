from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID

from app.schemas.reservation import ReservationResponse


class InventoryRepository(Protocol):
    def get_quantity_for_update(self, inventory_id: UUID) -> int | None: ...
    def set_quantity(self, inventory_id: UUID, quantity: int) -> None: ...


class ReservationRepository(Protocol):
    def get_by_pair(
        self, order_id: UUID, inventory_id: UUID
    ) -> ReservationResponse | None: ...
    def try_create_reservation(
        self, order_id: UUID, inventory_id: UUID, quantity: int, status: str
    ) -> ReservationResponse | None: ...


class InventoryUnitOfWork(Protocol):
    @property
    def inventories(self) -> InventoryRepository: ...
    @property
    def reservations(self) -> ReservationRepository: ...
    def begin(self) -> AbstractContextManager[None]: ...
