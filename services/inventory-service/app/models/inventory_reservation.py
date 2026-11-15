from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.inventory import Inventory


def utc_now() -> datetime:
    return datetime.now(UTC)


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"
    __table_args__ = (
        UniqueConstraint(
            "order_id", "inventory_id", name="uq_inventory_reservations_order_inventory"
        ),
        CheckConstraint("quantity > 0", name="ck_inventory_reservations_quantity"),
        CheckConstraint(
            "status IN ('RESERVED', 'RELEASED', 'CONFIRMED')",
            name="ck_inventory_reservations_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    inventory_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("inventories.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    inventory: Mapped[Inventory] = relationship()
