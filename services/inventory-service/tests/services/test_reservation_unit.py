from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas.reservation import ReservationResponse
from app.services.exceptions import (
    DuplicateReservation,
    InsufficientStock,
    InventoryNotFound,
)
from app.services.reservation_service import ReservationService


class MemoryUnitOfWork:
    def __init__(self, quantity=5):
        self.quantity = quantity
        self.records = {}
        self.reservations = self
        self.inventories = self
        self.fail = False
        self.fail_commit = False

    @contextmanager
    def begin(self):
        quantity, reservations = self.quantity, self.records.copy()
        try:
            yield
            if self.fail_commit:
                raise RuntimeError("commit failure")
        except Exception:
            self.quantity, self.records = quantity, reservations
            raise

    def get_quantity_for_update(self, inventory_id):
        return self.quantity

    def has_reservation(self, order_id, inventory_id):
        return (order_id, inventory_id) in self.records

    def set_quantity(self, inventory_id, quantity):
        self.quantity = quantity

    def create_reservation(self, order_id, inventory_id, quantity, status):
        if self.fail:
            raise RuntimeError("write failure")
        now = datetime.now(UTC)
        result = ReservationResponse(
            id=uuid4(),
            order_id=order_id,
            inventory_id=inventory_id,
            quantity=quantity,
            status=status,
            created_at=now,
            updated_at=now,
        )
        self.records[(order_id, inventory_id)] = result
        return result


def test_rules_and_rollback_with_memory_unit_of_work():
    uow, order_id, inventory_id = MemoryUnitOfWork(), uuid4(), uuid4()
    result = ReservationService(uow).reserve(order_id, inventory_id, 3)
    assert result.quantity == 3 and uow.quantity == 2
    with pytest.raises(DuplicateReservation):
        ReservationService(uow).reserve(order_id, inventory_id, 1)
    with pytest.raises(InsufficientStock):
        ReservationService(uow).reserve(uuid4(), inventory_id, 3)
    uow.fail = True
    with pytest.raises(RuntimeError):
        ReservationService(uow).reserve(uuid4(), inventory_id, 1)
    assert uow.quantity == 2 and list(uow.records.values()) == [result]


def test_missing_inventory_and_failed_commit_leave_state_unchanged():
    uow, inventory_id = MemoryUnitOfWork(), uuid4()
    uow.quantity = None
    with pytest.raises(InventoryNotFound):
        ReservationService(uow).reserve(uuid4(), inventory_id, 1)
    assert uow.records == {}
    uow.quantity = 5
    uow.fail_commit = True
    with pytest.raises(RuntimeError, match="commit failure"):
        ReservationService(uow).reserve(uuid4(), inventory_id, 2)
    assert uow.quantity == 5 and uow.records == {}
