"""Prediction API routes — Phase 3 implementation."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.team import Team
from app.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)

router = APIRouter()

_prediction_service: Optional[PredictionService] = None


def _get_prediction_service() -> PredictionService:
    global _prediction_service
    if _prediction_service is None:
        _prediction_service = PredictionService()
    return _prediction_service


class MatchPredictRequest(BaseModel):
    home_team_id: int
    away_team_id: int
    home_team_code: Optional[str] = None
    away_team_code: Optional[str] = None


async def _resolve_team(
    db: AsyncSession,
    team_id: int,
    fifa_code: Optional[str],
) -> Optional[Team]:
    """Resolve a team by ID, falling back to its stable FIFA code.

    Bracket data can remain cached in the browser while a development database
    is recreated, which makes autoincrement IDs stale. FIFA codes are stable
    across database rebuilds and let the request recover safely.
    """
    team = await db.get(Team, team_id)
    if team or not fifa_code:
        return team

    result = await db.execute(
        select(Team).where(Team.fifa_code == fifa_code.upper())
    )
    return result.scalar_one_or_none()


@router.get("/champion")
async def get_champion_prediction():
    return {"message": "Phase 4 implementation"}


@router.post("/match")
async def predict_match(
    req: MatchPredictRequest,
    db: AsyncSession = Depends(get_db),
):
    home = await _resolve_team(db, req.home_team_id, req.home_team_code)
    away = await _resolve_team(db, req.away_team_id, req.away_team_code)

    if not home:
        raise HTTPException(status_code=404, detail=f"Home team ID={req.home_team_id} not found")
    if not away:
        raise HTTPException(status_code=404, detail=f"Away team ID={req.away_team_id} not found")

    result = await _get_prediction_service().predict_match(
        home_team=home.name,
        away_team=away.name,
        db_session=db,
    )

    return {
        "home_team": home.name,
        "away_team": away.name,
        "is_valid": result.is_valid,
        "is_agent": result.is_agent,
        "model_used": result.model_used,
        "errors": result.errors,
        "warnings": result.warnings,
        "prediction": result.cleaned_data.model_dump() if result.cleaned_data else None,
        "circuit_breaker": _get_prediction_service().breaker.get_stats(),
    }


@router.get("/match/{match_id}")
async def get_match_prediction(match_id: int):
    return {"status": "stub", "match_id": match_id, "message": "Phase 4 implementation"}


@router.post("/recalculate")
async def recalculate_predictions():
    return {"status": "stub", "message": "Recalculation endpoint"}


@router.get("/bracket")
async def get_bracket_predictions():
    return {"message": "Phase 4 implementation"}
