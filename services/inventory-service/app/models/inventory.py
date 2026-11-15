from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Inventory(Base):
    __tablename__ = "inventories"
    __table_args__ = (
        CheckConstraint(
            "quantity_available >= 0", name="ck_inventories_quantity_available"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    product_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id"), unique=True, nullable=True
    )
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False)
