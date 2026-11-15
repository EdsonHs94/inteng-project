from uuid import uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models import Inventory
from app.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.repositories.reservation_repository import SqlAlchemyReservationRepository


def test_repositories_share_caller_transaction(migrated_engine: Engine) -> None:
    inventory_id, order_id = uuid4(), uuid4()
    with Session(migrated_engine) as session:
        session.add(Inventory(id=inventory_id, quantity_available=5))
        session.commit()
    with Session(migrated_engine) as session:
        inventories = SqlAlchemyInventoryRepository(session)
        reservations = SqlAlchemyReservationRepository(session)
        assert inventories.get_quantity_for_update(uuid4()) is None
        assert inventories.get_quantity_for_update(inventory_id) == 5
        assert not reservations.has_reservation(order_id, inventory_id)
        inventories.set_quantity(inventory_id, 2)
        reservation = reservations.create_reservation(
            order_id, inventory_id, 3, "RESERVED"
        )
        assert reservation.id is not None
        assert reservations.has_reservation(order_id, inventory_id)
        session.rollback()
    with Session(migrated_engine) as session:
        assert session.get(Inventory, inventory_id).quantity_available == 5
        assert not SqlAlchemyReservationRepository(session).has_reservation(
            order_id, inventory_id
        )
