from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.schemas.reservation import ReservationRequest, ReservationResponse
from app.services.reservation import (
    DuplicateReservation,
    InsufficientStock,
    InventoryNotFound,
    reserve,
)

router = APIRouter()


@router.post(
    "/reservations",
    status_code=status.HTTP_201_CREATED,
    response_model=ReservationResponse,
)
def create_reservation(
    payload: ReservationRequest, session: Annotated[Session, Depends(get_session)]
) -> ReservationResponse:
    try:
        result = reserve(
            session, payload.order_id, payload.inventory_id, payload.quantity
        )
    except InventoryNotFound as exc:
        raise HTTPException(status_code=404, detail="Inventory not found") from exc
    except DuplicateReservation as exc:
        raise HTTPException(
            status_code=409, detail="Reservation already exists"
        ) from exc
    except InsufficientStock as exc:
        raise HTTPException(status_code=409, detail="Insufficient stock") from exc
    return ReservationResponse.model_validate(result, from_attributes=True)
