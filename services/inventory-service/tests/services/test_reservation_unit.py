from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.services.reservation import (
    DuplicateReservation,
    InsufficientStock,
    InventoryNotFound,
    ReservationResult,
    reserve,
)


class MemoryUnitOfWork:
    def __init__(self, quantity=5):
        self.quantity = quantity
        self.reservations = {}
        self.fail = False
        self.fail_commit = False

    @contextmanager
    def begin(self):
        quantity, reservations = self.quantity, self.reservations.copy()
        try:
            yield
            if self.fail_commit:
                raise RuntimeError("commit failure")
        except Exception:
            self.quantity, self.reservations = quantity, reservations
            raise

    def get_quantity_for_update(self, inventory_id):
        return self.quantity

    def has_reservation(self, order_id, inventory_id):
        return (order_id, inventory_id) in self.reservations

    def set_quantity(self, inventory_id, quantity):
        self.quantity = quantity

    def create_reservation(self, order_id, inventory_id, quantity, status):
        if self.fail:
            raise RuntimeError("write failure")
        now = datetime.now(UTC)
        result = ReservationResult(
            uuid4(), order_id, inventory_id, quantity, status, now, now
        )
        self.reservations[(order_id, inventory_id)] = result
        return result


def test_rules_and_rollback_with_memory_unit_of_work():
    uow, order_id, inventory_id = MemoryUnitOfWork(), uuid4(), uuid4()
    result = reserve(uow, order_id, inventory_id, 3)
    assert result.quantity == 3 and uow.quantity == 2
    with pytest.raises(DuplicateReservation):
        reserve(uow, order_id, inventory_id, 1)
    with pytest.raises(InsufficientStock):
        reserve(uow, uuid4(), inventory_id, 3)
    uow.fail = True
    with pytest.raises(RuntimeError):
        reserve(uow, uuid4(), inventory_id, 1)
    assert uow.quantity == 2 and list(uow.reservations.values()) == [result]


def test_missing_inventory_and_failed_commit_leave_state_unchanged():
    uow, inventory_id = MemoryUnitOfWork(), uuid4()
    uow.quantity = None
    with pytest.raises(InventoryNotFound):
        reserve(uow, uuid4(), inventory_id, 1)
    assert uow.reservations == {}
    uow.quantity = 5
    uow.fail_commit = True
    with pytest.raises(RuntimeError, match="commit failure"):
        reserve(uow, uuid4(), inventory_id, 2)
    assert uow.quantity == 5 and uow.reservations == {}
