from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InventoryReservation
from app.schemas.reservation import ReservationResponse


class SqlAlchemyReservationRepository:
    def __init__(self, session: Session):
        self.session = session

    def has_reservation(self, order_id: UUID, inventory_id: UUID) -> bool:
        return (
            self.session.scalar(
                select(InventoryReservation.id).where(
                    InventoryReservation.order_id == order_id,
                    InventoryReservation.inventory_id == inventory_id,
                )
            )
            is not None
        )

    def create_reservation(
        self, order_id: UUID, inventory_id: UUID, quantity: int, status: str
    ) -> ReservationResponse:
        row = InventoryReservation(
            order_id=order_id,
            inventory_id=inventory_id,
            quantity=quantity,
            status=status,
        )
        self.session.add(row)
        self.session.flush()
        return ReservationResponse.model_validate(row, from_attributes=True)
