"""Prediction API routes — Phase 3 implementation."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.schema.prediction_schema import (
    SimulatedMatchAnalysisRequest,
    SimulatedMatchAnalysisResponse,
)
from app.services.prediction_service import PredictionService
from app.services.simulation_cache import get_simulation_cache

logger = logging.getLogger(__name__)

router = APIRouter()

_prediction_service: Optional[PredictionService] = None


def _get_prediction_service() -> PredictionService:
    global _prediction_service
    if _prediction_service is None:
        _prediction_service = PredictionService()
    return _prediction_service


@router.post("/match", response_model=SimulatedMatchAnalysisResponse)
async def predict_match(
    req: SimulatedMatchAnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    simulation = get_simulation_cache().get_by_id(req.simulation_id)
    if simulation is None:
        raise HTTPException(
            status_code=404,
            detail="模拟上下文不存在或已过期，请重新加载对阵图",
        )
    service = _get_prediction_service()
    math_context = service.resolve_simulated_match(simulation, req.match_key)
    if math_context is None:
        raise HTTPException(
            status_code=404,
            detail=f"当前模拟中不存在比赛 {req.match_key}",
        )
    agent_analysis = await service.analyze_simulated_match(math_context, db)
    return SimulatedMatchAnalysisResponse(
        simulation_id=req.simulation_id,
        match_key=req.match_key,
        math=math_context,
        agent=agent_analysis,
        circuit_breaker=service.breaker.get_stats(),
    )
