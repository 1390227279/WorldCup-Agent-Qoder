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

from scipy.stats import poisson as poisson_distribution
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.config import settings
from app.schema.prediction_schema import (
    MatchAgentAnalysis,
    MatchMathContext,
    ValidationResult,
    ValidatedPrediction,
    ReasoningStep,
)
from app.services.agent_service import AgentService
from app.services.circuit_breaker import CircuitBreaker
from app.services.poisson_predictor import PoissonPredictor
from app.services.monte_carlo import calculate_match_lambdas
from app.services.simulation_cache import CachedSimulation

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

            if result.is_valid and result.cleaned_data and not result.cleaned_data.predicted_score:
                result.cleaned_data.predicted_score = await self._predict_fallback_score(
                    home_team, away_team, db_session,
                )
                result.warnings.append("智能预测未返回有效比分，已使用统计模型补全")

            # AgentService 内部可能已经走了泊松降级（is_agent=False）
            if result.is_agent and result.is_valid:
                self.breaker.record_success()
                logger.info(
                    "Agent 预测成功 (%.1fs): %s vs %s → %s",
                    elapsed, home_team, away_team,
                    result.cleaned_data.winner if result.cleaned_data else "?",
                )
            elif not result.is_agent:
                if not result.is_valid or not result.cleaned_data:
                    result = await self._fallback_to_poisson(
                        home_team, away_team, db_session,
                    )
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

    def resolve_simulated_match(
        self,
        simulation: CachedSimulation,
        match_key: str,
    ) -> MatchMathContext | None:
        """从缓存模拟中解析权威比赛结果及其数学上下文。"""
        response = simulation.response
        stages = response["representative_path"]["stages"]
        match = next(
            (
                candidate
                for stage in stages.values()
                for candidate in stage["matches"]
                if candidate["match_key"] == match_key
            ),
            None,
        )
        if match is None:
            return None

        home = match["home_team"]
        away = match["away_team"]
        home_lambda, away_lambda = calculate_match_lambdas(
            home["elo_rating"],
            away["elo_rating"],
            home["fifa_code"],
            away["fifa_code"],
            response["scenario"]["team_impacts"],
        )
        probabilities = self._outcome_probabilities(
            home_lambda,
            away_lambda,
            home["elo_rating"],
            away["elo_rating"],
        )
        team_ids = {home["id"], away["id"]}
        relevant_events = [
            event
            for event in response["scenario"]["applied_events"]
            if event["team_id"] in team_ids
        ]
        return MatchMathContext(
            simulation_id=simulation.simulation_id,
            match_key=match_key,
            scenario_type=response["scenario"]["type"],
            stage=match["stage"],
            round_name=match["round_name"],
            home_team=home,
            away_team=away,
            predicted_score=f'{match["home_score"]}-{match["away_score"]}',
            winner_team_id=match["winner_team_id"],
            winner=match["winner"],
            decided_by=match["decided_by"],
            home_lambda=round(home_lambda, 4),
            away_lambda=round(away_lambda, 4),
            probabilities=probabilities,
            applied_events=relevant_events,
        )

    async def analyze_simulated_match(
        self,
        math_context: MatchMathContext,
        db_session: AsyncSession,
    ) -> MatchAgentAnalysis:
        """调用 Qwen 解释数学结果；任何失败都返回结构化不可用状态。"""
        if self.breaker.is_open():
            return self._agent_unavailable("智能分析熔断中，数学结果仍然有效")
        try:
            result = await self.agent.analyze_simulated_match(
                math_context.model_dump(),
                db_session,
            )
            if not result.is_valid or result.cleaned_data is None:
                self.breaker.record_failure()
                return self._agent_unavailable(
                    "智能分析返回格式无效，数学结果仍然有效",
                    warnings=result.errors + result.warnings,
                )
            self.breaker.record_success()
            report = result.cleaned_data
            return MatchAgentAnalysis(
                status="available",
                model_used=settings.qwen_model,
                key_factors=report.key_factors,
                risk_notes=report.risk_notes,
                reasoning_chain=report.reasoning_chain,
                tool_calls_log=report.tool_calls_log,
                warnings=result.warnings,
            )
        except Exception as exc:
            self.breaker.record_failure()
            logger.error("模拟比赛智能分析失败: %s", exc)
            return self._agent_unavailable(
                "智能分析暂时不可用，数学结果仍然有效"
            )

    @staticmethod
    def _agent_unavailable(
        message: str,
        warnings: Optional[list[str]] = None,
    ) -> MatchAgentAnalysis:
        return MatchAgentAnalysis(
            status="agent_unavailable",
            message=message,
            warnings=warnings or [],
        )

    @staticmethod
    def _outcome_probabilities(
        home_lambda: float,
        away_lambda: float,
        home_elo: float,
        away_elo: float,
    ) -> dict[str, float]:
        home_win = draw = away_win = 0.0
        for home_goals in range(11):
            home_probability = poisson_distribution.pmf(home_goals, home_lambda)
            for away_goals in range(11):
                probability = home_probability * poisson_distribution.pmf(
                    away_goals,
                    away_lambda,
                )
                if home_goals > away_goals:
                    home_win += probability
                elif home_goals == away_goals:
                    draw += probability
                else:
                    away_win += probability
        total = home_win + draw + away_win
        home_win, draw, away_win = (
            home_win / total,
            draw / total,
            away_win / total,
        )
        home_penalty_probability = 1.0 / (
            1.0 + 10.0 ** ((away_elo - home_elo) / 400.0)
        )
        home_advance = home_win + draw * home_penalty_probability
        return {
            "home_win": round(home_win, 4),
            "draw": round(draw, 4),
            "away_win": round(away_win, 4),
            "home_advance": round(home_advance, 4),
            "away_advance": round(1.0 - home_advance, 4),
        }

    async def _predict_fallback_score(
        self,
        home_team: str,
        away_team: str,
        db_session: AsyncSession,
    ) -> str:
        stmt = select(Team).where(Team.name.in_([home_team, away_team]))
        rows = (await db_session.execute(stmt)).scalars().all()
        teams_map = {team.name: team for team in rows}
        home = teams_map.get(home_team)
        away = teams_map.get(away_team)
        home_elo = home.elo_rating if home and home.elo_rating else 1500.0
        away_elo = away.elo_rating if away and away.elo_rating else 1500.0
        return self.poisson.predict_score(
            home_team, away_team, home_elo, away_elo,
        ).most_likely_score

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
