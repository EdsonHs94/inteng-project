from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.repositories.unit_of_work import SqlAlchemyInventoryUnitOfWork
from app.services.reservation_service import ReservationService


def get_reservation_service(
    session: Annotated[Session, Depends(get_session)],
) -> ReservationService:
    return ReservationService(SqlAlchemyInventoryUnitOfWork(session))
