"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models import init_db
from app.routers import teams, predictions, bracket, events, provenance


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and seed data on startup."""
    await init_db()
    yield


app = FastAPI(
    title="世界杯情景预测系统",
    description="基于 ELO、泊松模型和蒙特卡洛模拟的世界杯情景推演；Qwen 仅生成单场战术解释",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(teams.router, prefix="/api/v1/teams", tags=["teams"])
app.include_router(predictions.router, prefix="/api/v1/predictions", tags=["predictions"])
app.include_router(bracket.router, prefix="/api/v1/bracket", tags=["bracket"])
app.include_router(events.router, prefix="/api/v1/events", tags=["events"])
app.include_router(provenance.router, prefix="/api/v1/data-sources", tags=["data-sources"])


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint for deployment monitoring."""
    return {"status": "healthy", "version": "2.0.0", "agent": "qwen-max"}
