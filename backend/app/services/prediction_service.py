"""Resolve simulated matches and request optional Qwen explanations."""

from __future__ import annotations

import logging
from typing import Optional

from scipy.stats import poisson as poisson_distribution
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schema.prediction_schema import MatchAgentAnalysis, MatchMathContext
from app.services.agent_service import AgentService
from app.services.circuit_breaker import CircuitBreaker
from app.services.monte_carlo import calculate_match_lambdas
from app.services.simulation_cache import CachedSimulation

logger = logging.getLogger(__name__)


class PredictionService:
    """Keep deterministic match mathematics separate from optional AI text."""

    def __init__(
        self,
        agent_service: Optional[AgentService] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.agent = agent_service or AgentService()
        self.breaker = circuit_breaker or CircuitBreaker()

    def resolve_simulated_match(
        self,
        simulation: CachedSimulation,
        match_key: str,
    ) -> MatchMathContext | None:
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
        team_ids = {home["id"], away["id"]}
        relevant_math_events = [
            event
            for event in response["scenario"]["math_events"]
            if event["team_id"] in team_ids
        ]
        relevant_narrative_events = [
            event
            for event in response["scenario"]["narrative_events"]
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
            probabilities=self._outcome_probabilities(
                home_lambda,
                away_lambda,
                home["elo_rating"],
                away["elo_rating"],
            ),
            math_events=relevant_math_events,
            narrative_events=relevant_narrative_events,
        )

    async def analyze_simulated_match(
        self,
        math_context: MatchMathContext,
        db_session: AsyncSession,
    ) -> MatchAgentAnalysis:
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
            return self._agent_unavailable("智能分析暂时不可用，数学结果仍然有效")

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
        home_win, draw, away_win = home_win / total, draw / total, away_win / total
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
