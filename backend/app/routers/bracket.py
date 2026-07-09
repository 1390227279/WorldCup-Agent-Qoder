"""Bracket API routes (stubs — Phase 3 fill)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def get_bracket():
    """Return complete tournament bracket tree with predictions."""
    return {"status": "stub", "message": "Bracket API coming in Phase 3"}


@router.get("/simulation")
async def get_simulation_results():
    """Return Monte Carlo simulation results (champion probabilities)."""
    return {"status": "stub", "message": "Simulation API coming in Phase 3"}
