"""Prediction API routes — Phase 3 实现。"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.team import Team
from app.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)

router = APIRouter()

# ── 单例服务（模块级复用） ────────────────────────────────
_prediction_service = PredictionService()


# ── 请求体 ────────────────────────────────────────────────

class MatchPredictRequest(BaseModel):
    """POST /predictions/match 请求体。"""
    home_team_id: int
    away_team_id: int


# ── 路由 ──────────────────────────────────────────────────

@router.get("/champion")
async def get_champion_prediction():
    """Return the current champion prediction with reasoning."""
    # 桩 — Phase 4 实现
    return {"message": "Phase 4 实现"}


@router.post("/match")
async def predict_match(
    req: MatchPredictRequest,
    db: AsyncSession = Depends(get_db),
):
    """接收两队 ID，调用 PredictionService 返回预测结果。

    流程：
      1. 根据 team_id 查询球队名称
      2. 调用 PredictionService.predict_match()
      3. 返回 ValidationResult
    """
    # 查询两队
    home = await db.get(Team, req.home_team_id)
    away = await db.get(Team, req.away_team_id)

    if not home:
        raise HTTPException(status_code=404, detail=f"主队 ID={req.home_team_id} 不存在")
    if not away:
        raise HTTPException(status_code=404, detail=f"客队 ID={req.away_team_id} 不存在")

    # 调用编排层
    result = await _prediction_service.predict_match(
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
        "circuit_breaker": _prediction_service.breaker.get_stats(),
    }


@router.get("/match/{match_id}")
async def get_match_prediction(match_id: int):
    """Return Agent prediction for a specific match."""
    # 桩 — Phase 4 实现（需要从 predictions 表读取历史预测）
    return {"status": "stub", "match_id": match_id, "message": "Phase 4 实现"}


@router.post("/recalculate")
async def recalculate_predictions():
    """Trigger a full prediction recalculation (e.g. after event changes)."""
    return {"status": "stub", "message": "Recalculation endpoint"}


@router.get("/bracket")
async def get_bracket_predictions():
    """Return predictions for all bracket matches."""
    # 桩 — Phase 4 实现
    return {"message": "Phase 4 实现"}
