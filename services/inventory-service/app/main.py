from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.reservations import router as reservations_router
from app.core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(title="Inventory Service", lifespan=lifespan)
app.include_router(health_router)
app.include_router(reservations_router)
