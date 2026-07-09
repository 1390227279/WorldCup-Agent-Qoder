"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models import init_db
from app.routers import teams, predictions, bracket, events


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and seed data on startup."""
    await init_db()
    yield


app = FastAPI(
    title="WorldCup Predictor Agent",
    description="AI-powered FIFA World Cup 2026 prediction engine — Qwen Agent as decision core",
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


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint for deployment monitoring."""
    return {"status": "healthy", "version": "2.0.0", "agent": "qwen-max"}
