"""Prediction API routes (stubs — Phase 2 fill)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/champion")
async def get_champion_prediction():
    """Return the current champion prediction with reasoning."""
    # Stub — will be filled in Phase 2/3
    return {"status": "not yet predicted", "message": "Prediction engine coming in Phase 2"}


@router.get("/match/{match_id}")
async def get_match_prediction(match_id: int):
    """Return Agent prediction for a specific match."""
    return {"status": "stub", "match_id": match_id}


@router.post("/recalculate")
async def recalculate_predictions():
    """Trigger a full prediction recalculation (e.g. after event changes)."""
    return {"status": "stub", "message": "Recalculation endpoint"}
