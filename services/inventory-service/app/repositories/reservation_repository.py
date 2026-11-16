from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import InventoryReservation
from app.schemas.reservation import ReservationResponse


class SqlAlchemyReservationRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_pair(
        self, order_id: UUID, inventory_id: UUID
    ) -> ReservationResponse | None:
        row = self.session.scalar(
            select(InventoryReservation).where(
                InventoryReservation.order_id == order_id,
                InventoryReservation.inventory_id == inventory_id,
            )
        )
        return (
            ReservationResponse.model_validate(row, from_attributes=True)
            if row is not None
            else None
        )

    def try_create_reservation(
        self, order_id: UUID, inventory_id: UUID, quantity: int, status: str
    ) -> ReservationResponse | None:
        statement = (
            insert(InventoryReservation)
            .values(
                order_id=order_id,
                inventory_id=inventory_id,
                quantity=quantity,
                status=status,
            )
            .on_conflict_do_nothing(
                constraint="uq_inventory_reservations_order_inventory"
            )
            .returning(InventoryReservation)
        )
        row = self.session.scalar(statement)
        return (
            ReservationResponse.model_validate(row, from_attributes=True)
            if row is not None
            else None
        )
