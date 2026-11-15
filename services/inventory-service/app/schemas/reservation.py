from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ReservationRequest(BaseModel):
    order_id: UUID
    inventory_id: UUID
    quantity: int = Field(gt=0, le=2147483647)


class ReservationResponse(BaseModel):
    id: UUID
    order_id: UUID
    inventory_id: UUID
    quantity: int
    status: str
    created_at: datetime
    updated_at: datetime
