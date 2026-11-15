from uuid import UUID, uuid4

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    sku: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
