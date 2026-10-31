from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models
from app.database import Base, StateBase, engine, state_engine
from app.routers import (
    arithmetic_router,
    chart_state_router,
    explode_router,
    fractal_router,
    indicator_router,
    symbol_router,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    StateBase.metadata.create_all(bind=state_engine)
    yield


app = FastAPI(title="TradingView 2.0 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(symbol_router.router)
app.include_router(chart_state_router.router)
app.include_router(arithmetic_router.router)
app.include_router(explode_router.router)
app.include_router(indicator_router.router)
app.include_router(fractal_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
