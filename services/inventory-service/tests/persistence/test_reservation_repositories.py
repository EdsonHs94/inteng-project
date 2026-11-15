from uuid import uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models import Inventory, InventoryReservation
from app.repositories import inventory, inventory_reservation


def test_repositories_share_caller_transaction(migrated_engine: Engine) -> None:
    inventory_id, order_id = uuid4(), uuid4()
    with Session(migrated_engine) as session:
        session.add(Inventory(id=inventory_id, quantity_available=5))
        session.commit()
    with Session(migrated_engine) as session:
        assert inventory.get_for_update(session, uuid4()) is None
        row = inventory.get_for_update(session, inventory_id)
        assert row is not None
        assert (
            inventory_reservation.find_by_pair(session, order_id, inventory_id) is None
        )
        inventory.set_quantity(session, row, 2)
        reservation = InventoryReservation(
            order_id=order_id, inventory_id=inventory_id, quantity=3, status="RESERVED"
        )
        inventory_reservation.add(session, reservation)
        assert (
            inventory_reservation.find_by_pair(session, order_id, inventory_id).id
            == reservation.id
        )
        session.rollback()
    with Session(migrated_engine) as session:
        assert session.get(Inventory, inventory_id).quantity_available == 5
        assert (
            inventory_reservation.find_by_pair(session, order_id, inventory_id) is None
        )
