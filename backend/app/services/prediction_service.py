"""
Prediction Service — 容错编排层

将 Agent 预测（Qwen）、熔断器、泊松降级串成一个完整的容错流程：
  1. 检查熔断器 → 若已熔断直接走 Poisson
  2. 调用 AgentService.predict_match()（Qwen Agent）
  3. 捕获异常 → 记录失败 → 降级到 PoissonPredictor
  4. 返回 ValidationResult

这是路由层直接调用的服务，屏蔽了 Agent / 熔断 / 降级的复杂性。
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.schema.prediction_schema import (
    ValidationResult,
    ValidatedPrediction,
    ReasoningStep,
)
from app.services.agent_service import AgentService
from app.services.circuit_breaker import CircuitBreaker
from app.services.poisson_predictor import PoissonPredictor

from sqlalchemy import select

logger = logging.getLogger(__name__)


class PredictionService:
    """Agent 优先 + 降级的容错预测编排。

    Usage:
        service = PredictionService()
        result = await service.predict_match("Argentina", "Brazil", db_session)
        if result.is_valid:
            print(result.cleaned_data.winner)
    """

    def __init__(
        self,
        agent_service: Optional[AgentService] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        poisson_predictor: Optional[PoissonPredictor] = None,
    ) -> None:
        self.agent = agent_service or AgentService()
        self.breaker = circuit_breaker or CircuitBreaker()
        self.poisson = poisson_predictor or PoissonPredictor()

    async def predict_match(
        self,
        home_team: str,
        away_team: str,
        db_session: AsyncSession,
    ) -> ValidationResult:
        """预测一场比赛，Agent 优先，失败自动降级到泊松。

        流程：
          a. 检查熔断器 → 若 OPEN 直接走 Poisson
          b. 调用 AgentService.predict_match()
          c. 成功 → record_success；异常 → record_failure + 降级 Poisson
          d. 返回 ValidationResult

        Args:
            home_team: 主队英文名。
            away_team: 客队英文名。
            db_session: 数据库异步会话。

        Returns:
            ValidationResult（is_agent=True 表示 Agent 预测，False 表示泊松降级）。
        """
        # ── Step a: 熔断器检查 ──────────────────────────────
        if self.breaker.is_open():
            logger.warning(
                "熔断器已开启，跳过 Agent，直接使用泊松降级: %s vs %s",
                home_team, away_team,
            )
            return await self._fallback_to_poisson(home_team, away_team, db_session)

        # ── Step b: 调用 Agent ──────────────────────────────
        try:
            t0 = time.time()
            result = await self.agent.predict_match(home_team, away_team, db_session)
            elapsed = time.time() - t0

            # AgentService 内部可能已经走了泊松降级（is_agent=False）
            if result.is_agent and result.is_valid:
                self.breaker.record_success()
                logger.info(
                    "Agent 预测成功 (%.1fs): %s vs %s → %s",
                    elapsed, home_team, away_team,
                    result.cleaned_data.winner if result.cleaned_data else "?",
                )
            elif not result.is_agent:
                # AgentService 内部已降级，不算 API 失败
                logger.info(
                    "AgentService 内部已降级到泊松 (%.1fs): %s vs %s",
                    elapsed, home_team, away_team,
                )
            else:
                # Agent 返回了但校验失败
                self.breaker.record_failure()
                logger.warning(
                    "Agent 返回校验失败 (%.1fs): %s vs %s, errors=%s",
                    elapsed, home_team, away_team, result.errors,
                )
                # 校验失败也降级到泊松
                result = await self._fallback_to_poisson(home_team, away_team, db_session)

            return result

        except Exception as exc:
            # ── Step c: 异常降级 ────────────────────────────
            self.breaker.record_failure()
            logger.error(
                "Agent 预测异常，降级到泊松: %s vs %s, error=%s",
                home_team, away_team, exc,
            )
            return await self._fallback_to_poisson(home_team, away_team, db_session)

    async def _fallback_to_poisson(
        self,
        home_team: str,
        away_team: str,
        db_session: AsyncSession,
    ) -> ValidationResult:
        """泊松降级预测。

        从数据库查询两队 ELO，调用 PoissonPredictor，
        包装成 ValidationResult 返回（is_agent=False）。
        """
        try:
            # 查询两队 ELO
            stmt = select(Team).where(Team.name.in_([home_team, away_team]))
            rows = (await db_session.execute(stmt)).scalars().all()
            teams_map = {t.name: t for t in rows}

            home = teams_map.get(home_team)
            away = teams_map.get(away_team)

            home_elo = home.elo_rating if home and home.elo_rating else 1500.0
            away_elo = away.elo_rating if away and away.elo_rating else 1500.0

            # 泊松预测
            score_pred = self.poisson.predict_score(
                home_team, away_team, home_elo, away_elo,
            )

            # 决定 winner
            if score_pred.home_win_prob > score_pred.away_win_prob:
                winner = home_team
            elif score_pred.away_win_prob > score_pred.home_win_prob:
                winner = away_team
            else:
                winner = "draw"

            # confidence = 最大概率
            confidence = max(
                score_pred.home_win_prob,
                score_pred.draw_prob,
                score_pred.away_win_prob,
            )

            cleaned = ValidatedPrediction(
                winner=winner,
                predicted_score=score_pred.most_likely_score,
                confidence=round(confidence, 4),
                key_factors=[
                    f"泊松统计模型预测（主队ELO={home_elo:.0f}，客队ELO={away_elo:.0f}）",
                    f"主队预期进球 {score_pred.home_expected_goals:.2f}，"
                    f"客队预期进球 {score_pred.away_expected_goals:.2f}",
                    f"胜率分布: 主{score_pred.home_win_prob:.1%} / "
                    f"平{score_pred.draw_prob:.1%} / 客{score_pred.away_win_prob:.1%}",
                ],
                reasoning_chain=[
                    ReasoningStep(
                        step_number=1,
                        tool_used="poisson_predictor",
                        finding=f"泊松降级预测: {home_team} vs {away_team}",
                        analysis=f"ELO {home_elo:.0f} vs {away_elo:.0f}，"
                                 f"最可能比分 {score_pred.most_likely_score}",
                    ),
                ],
            )

            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=["Agent 不可用，已降级到泊松统计模型"],
                cleaned_data=cleaned,
                model_used="poisson",
                is_agent=False,
            )

        except Exception as exc:
            logger.error("泊松降级也失败: %s", exc)
            return ValidationResult(
                is_valid=False,
                errors=[f"Agent 和泊松均失败: {exc}"],
                warnings=[],
                cleaned_data=None,
                model_used="none",
                is_agent=False,
            )
