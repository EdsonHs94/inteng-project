from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import get_reservation_service
from app.schemas.reservation import ReservationRequest, ReservationResponse
from app.services.exceptions import (
    DuplicateReservation,
    InsufficientStock,
    InventoryNotFound,
)
from app.services.reservation_service import ReservationService

router = APIRouter()


@router.post(
    "/reservations",
    status_code=status.HTTP_201_CREATED,
    response_model=ReservationResponse,
    responses={status.HTTP_200_OK: {"model": ReservationResponse}},
)
def create_reservation(
    payload: ReservationRequest,
    response: Response,
    service: Annotated[ReservationService, Depends(get_reservation_service)],
) -> ReservationResponse:
    try:
        result, created = service.reserve(
            payload.order_id, payload.inventory_id, payload.quantity
        )
    except InventoryNotFound as exc:
        raise HTTPException(status_code=404, detail="Inventory not found") from exc
    except DuplicateReservation as exc:
        raise HTTPException(
            status_code=409, detail="Reservation quantity or status conflicts"
        ) from exc
    except InsufficientStock as exc:
        raise HTTPException(status_code=409, detail="Insufficient stock") from exc
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return result
