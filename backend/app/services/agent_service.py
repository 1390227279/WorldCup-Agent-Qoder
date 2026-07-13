"""
Agent Service — Qwen Agent 编排核心

整个系统的决策中枢，负责编排完整的预测流程：
  System Prompt → 注入比赛上下文 → 调用 Qwen → 解析工具调用 →
  执行本地工具 → 回传结果 → 获取最终预测 → Pydantic 校验

设计原则（Agent-native）：
  - Qwen 是决策者，不是翻译官
  - Python 统计模型（ELO、泊松）降级为 Agent 的工具箱
  - 三层容错：Function Calling → Pydantic 校验 → CircuitBreaker 降级

依赖：QwenClient, ToolRegistry, CircuitBreaker, PoissonPredictor,
      EloEngine, EventInjector, DataCollector
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.team import Team
from app.schema.prediction_schema import (
    PredictionInput,
    ValidationResult,
    ValidatedPrediction,
    validate_prediction,
    ReasoningStep,
    ToolCallRecord,
)
from app.services.circuit_breaker import CircuitBreaker
from app.services.data_collector import DataCollector, BUILTIN_HISTORICAL_MATCHES, BUILTIN_FIFA_RANKINGS
from app.services.elo_engine import elo_to_win_probability, normalize_elo
from app.services.event_injector import EventInjector
from app.services.poisson_predictor import PoissonPredictor
from app.services.qwen_client import QwenClient, QwenAPIError, DashScopeResponse, ToolCall
from app.services.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


# ── System Prompt ─────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """你是一位资深足球分析师 AI Agent，专门预测 2026 年世界杯比赛结果。

## 你的角色
- 你是**决策者**，不是翻译官。Python 统计模型（ELO、泊松）只是你的参考工具
- 你需要综合多维度数据，独立做出预测判断
- 每个结论必须有数据支撑，不要凭直觉猜测

## 可用工具
你可以调用以下工具获取数据：
1. **get_elo_rating** — 获取球队 ELO 评分（综合实力指标）
2. **get_fifa_ranking** — 获取球队 FIFA 官方排名和积分
3. **get_recent_form** — 获取球队近期比赛战绩（状态趋势）
4. **get_h2h_record** — 获取两队历史交锋记录
5. **get_poisson_prediction** — 泊松分布统计模型预测（纯数学，不考虑动态因素）
6. **get_team_events** — 获取球队伤病、换帅等动态事件
7. **get_group_standings** — 获取小组积分排名

## 决策流程（请按此顺序分析）
1. 先查两队 **ELO 评分和 FIFA 排名**，建立实力基线
2. 查看两队 **近期状态**，判断当前竞技水平
3. 查看 **历史交锋**，识别克星关系和心理优势
4. 查看两队 **伤病/换帅事件**，评估动态影响
5. （可选）调用 **泊松模型**获取统计基线作为参考
6. **综合判断**：结合所有维度，给出你的预测

## 输出要求
分析完成后，你必须调用 **submit_prediction** 工具提交预测结果，参数包括：
- **winner**: 胜出球队英文名（或 "draw" 表示平局）
- **predicted_score**: 预测比分，如 "2-1"
- **confidence**: 置信度 0-1 之间
- **key_factors**: 3-5 个关键因素的中文描述列表
- **reasoning_chain**: 推理步骤列表，每步包含 step_number, tool_used, finding, analysis

## 注意事项
- 数据驱动，每个判断引用具体数字
- 如果泊松模型和你的判断不一致，说明你的理由
- CRITICAL 级别的伤病事件可能使球队实力下降 10-20%
- 历史交锋中如果有明显"克星"模式，需要加权考虑
"""

# 最大对话轮次（防止无限循环）
MAX_ROUNDS = 5


# ── Agent 编排服务 ────────────────────────────────────────

class AgentService:
    """Agent 预测编排核心服务。

    Usage:
        service = AgentService()
        result = await service.predict_match("Brazil", "Germany", db_session)
        if result.is_valid:
            prediction = result.cleaned_data
    """

    def __init__(
        self,
        qwen_client: Optional[QwenClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        poisson_predictor: Optional[PoissonPredictor] = None,
        data_collector: Optional[DataCollector] = None,
    ) -> None:
        """初始化 Agent 服务，所有依赖均可注入（方便测试）。"""
        self.qwen_client = qwen_client or QwenClient()
        self.tool_registry = tool_registry or ToolRegistry()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.poisson_predictor = poisson_predictor or PoissonPredictor()
        self.data_collector = data_collector or DataCollector()

    # ── 主预测流程 ────────────────────────────────────────

    async def predict_match(
        self,
        home_team: str,
        away_team: str,
        db_session: AsyncSession,
    ) -> ValidationResult:
        """预测一场比赛的完整 Agent 流程。

        流程：
          1. 检查熔断器 → 熔断则走泊松兜底
          2. 构建 system prompt + 比赛上下文
          3. 多轮对话：调用 Qwen → 执行工具 → 回传结果
          4. 解析 submit_prediction → Pydantic 校验
          5. 校验失败 → 降级到泊松

        Args:
            home_team: 主队英文名。
            away_team: 客队英文名。
            db_session: 数据库异步会话。

        Returns:
            ValidationResult（is_agent=True 表示 Agent 预测，False 表示泊松兜底）。
        """
        logger.info("=" * 60)
        logger.info("开始预测: %s vs %s", home_team, away_team)
        logger.info("=" * 60)

        # ── 1. 熔断器检查 ──
        if self.circuit_breaker.is_open():
            logger.warning("熔断器开启，直接走泊松兜底")
            return self._fallback_to_poisson(home_team, away_team)

        try:
            # ── 2. 构建初始消息 ──
            context = await self._build_match_context(home_team, away_team, db_session)
            messages = [
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ]

            # 获取工具列表（加入 submit_prediction 特殊工具）
            tools = self.tool_registry.get_tools()
            tools.append(self._submit_prediction_tool_def())

            # ── 3. 多轮对话循环 ──
            prediction_data: Optional[dict] = None
            all_tool_records: list[ToolCallRecord] = []

            for round_num in range(1, MAX_ROUNDS + 1):
                logger.info("--- 第 %d/%d 轮对话 ---", round_num, MAX_ROUNDS)

                response = await self.qwen_client.chat_with_tools(messages, tools)

                # 处理工具调用
                if response.tool_calls:
                    for tc in response.tool_calls:
                        # 检测 submit_prediction
                        if tc.name == "submit_prediction":
                            logger.info("Agent 提交预测结果")
                            prediction_data = tc.arguments
                            break

                        # 执行本地工具
                        start_ms = int(time.time() * 1000)
                        try:
                            tool_result = await self._execute_tool(
                                tc.name, tc.arguments, db_session,
                            )
                            success = True
                        except Exception as exc:
                            tool_result = f"工具执行失败: {exc}"
                            success = False
                            logger.error("工具 %s 执行失败: %s", tc.name, exc)

                        elapsed_ms = int(time.time() * 1000) - start_ms

                        all_tool_records.append(ToolCallRecord(
                            tool_name=tc.name,
                            input_params=tc.arguments,
                            output_summary=tool_result[:500] if len(tool_result) > 500 else tool_result,
                            execution_time_ms=elapsed_ms,
                            success=success,
                        ))

                        # 将工具结果追加到消息
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                                },
                            }],
                        })
                        messages.append({
                            "role": "tool",
                            "content": tool_result,
                            "tool_call_id": tc.id,
                        })

                    # 如果已提交预测，跳出循环
                    if prediction_data is not None:
                        break
                    continue

                # 无工具调用 → Qwen 直接回复了（可能包含 submit_prediction 的文本描述）
                if response.content:
                    logger.info("Agent 直接回复（无工具调用）")
                    prediction_data = self._try_parse_prediction_from_text(response.content)
                break

            # ── 4. 记录成功 ──
            self.circuit_breaker.record_success()

            # ── 5. 校验预测结果 ──
            if prediction_data is None:
                logger.warning("Agent 未返回预测结果，降级到泊松")
                return self._fallback_to_poisson(home_team, away_team)

            # 注入工具调用日志（如果 Agent 没有自己传）
            if "tool_calls_log" not in prediction_data or not prediction_data["tool_calls_log"]:
                prediction_data["tool_calls_log"] = [
                    {"tool_name": r.tool_name, "input_params": r.input_params,
                     "output_summary": r.output_summary, "execution_time_ms": r.execution_time_ms,
                     "success": r.success}
                    for r in all_tool_records
                ]

            logger.info("开始 Pydantic 校验")
            input_data = PredictionInput(**prediction_data)
            validation = validate_prediction(input_data)

            if validation.is_valid:
                logger.info("校验通过 ✓ winner=%s, confidence=%.2f",
                            validation.cleaned_data.winner,
                            validation.cleaned_data.confidence)
                return validation
            else:
                logger.warning("校验失败: %s → 降级到泊松", validation.errors)
                return self._fallback_to_poisson(home_team, away_team)

        except QwenAPIError as exc:
            logger.error("Qwen API 错误: %s", exc)
            self.circuit_breaker.record_failure()
            return self._fallback_to_poisson(home_team, away_team)

        except (TimeoutError, ConnectionError) as exc:
            logger.error("网络/超时错误: %s", exc)
            self.circuit_breaker.record_failure()
            return self._fallback_to_poisson(home_team, away_team)

        except Exception as exc:
            logger.exception("Agent 预测流程异常")
            self.circuit_breaker.record_failure()
            return self._fallback_to_poisson(home_team, away_team)

    # ── 工具执行路由 ──────────────────────────────────────

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        db_session: AsyncSession,
    ) -> str:
        """路由并执行本地工具调用，返回结果字符串。

        Args:
            tool_name: 工具名称。
            arguments: 工具参数。
            db_session: 数据库会话。

        Returns:
            工具执行结果的文本描述（供 Qwen 阅读）。
        """
        logger.info("执行工具: %s(%s)", tool_name, arguments)

        try:
            if tool_name == "get_elo_rating":
                return await self._tool_get_elo_rating(arguments, db_session)

            elif tool_name == "get_fifa_ranking":
                return await self._tool_get_fifa_ranking(arguments, db_session)

            elif tool_name == "get_recent_form":
                return self._tool_get_recent_form(arguments)

            elif tool_name == "get_h2h_record":
                return self._tool_get_h2h_record(arguments)

            elif tool_name == "get_poisson_prediction":
                return self._tool_get_poisson_prediction(arguments)

            elif tool_name == "get_team_events":
                return await self._tool_get_team_events(arguments, db_session)

            elif tool_name == "get_group_standings":
                return await self._tool_get_group_standings(arguments, db_session)

            else:
                return f"未知工具: {tool_name}"

        except Exception as exc:
            logger.error("工具 %s 执行异常: %s", tool_name, exc)
            return f"工具执行出错: {exc}"

    # ── 各工具实现 ────────────────────────────────────────

    async def _tool_get_elo_rating(self, args: dict, db: AsyncSession) -> str:
        """get_elo_rating: 从数据库查询球队 ELO 评分。"""
        team_name = args.get("team_name", "")
        result = await db.execute(
            select(Team).where(Team.name.ilike(f"%{team_name}%"))
        )
        team = result.scalars().first()
        if not team:
            return f"未找到球队: {team_name}"

        elo = team.elo_rating or 1500.0
        normalized = normalize_elo(elo)
        win_prob_vs_avg = elo_to_win_probability(elo, 1500.0)

        return (
            f"球队: {team.name} ({team.name_cn})\n"
            f"ELO 评分: {elo:.0f}\n"
            f"标准化评分: {normalized:.1f}/100\n"
            f"对阵平均实力球队胜率: {win_prob_vs_avg:.1%}\n"
            f"所属小组: {team.group_name or 'N/A'}\n"
            f"联盟: {team.confederation}"
        )

    async def _tool_get_fifa_ranking(self, args: dict, db: AsyncSession) -> str:
        """get_fifa_ranking: 查询球队 FIFA 排名。"""
        team_name = args.get("team_name", "")
        result = await db.execute(
            select(Team).where(Team.name.ilike(f"%{team_name}%"))
        )
        team = result.scalars().first()
        if not team:
            # 从内置数据查
            for r in BUILTIN_FIFA_RANKINGS:
                if r.fifa_code.lower() in team_name.lower() or team_name.lower() in r.fifa_code.lower():
                    return f"球队代码: {r.fifa_code}\nFIFA 排名: 第 {r.rank} 名\n积分: {r.points:.0f}"
            return f"未找到球队: {team_name}"

        ranking = team.fifa_ranking or 0
        # 从内置数据补充积分
        points = 0.0
        for r in BUILTIN_FIFA_RANKINGS:
            if r.fifa_code == team.fifa_code:
                points = r.points
                break

        return (
            f"球队: {team.name} ({team.name_cn})\n"
            f"FIFA 排名: 第 {ranking} 名\n"
            f"FIFA 积分: {points:.0f}\n"
            f"联盟: {team.confederation}"
        )

    def _tool_get_recent_form(self, args: dict) -> str:
        """get_recent_form: 从内置历史数据中查找球队近期战绩。"""
        team_name = args.get("team_name", "")
        n_matches = args.get("n_matches", 10)
        name_lower = team_name.lower()

        # 从内置比赛数据中查找
        matches = []
        for m in BUILTIN_HISTORICAL_MATCHES:
            # 匹配球队名或 FIFA 代码
            if (name_lower in m.home_team.lower() or name_lower in m.away_team.lower()
                    or m.home_team.lower() in name_lower or m.away_team.lower() in name_lower):
                matches.append(m)

        if not matches:
            return f"未找到 {team_name} 的历史比赛记录。"

        # 按日期倒序取最近 N 场
        matches.sort(key=lambda x: x.date, reverse=True)
        recent = matches[:n_matches]

        wins, draws, losses = 0, 0, 0
        lines = [f"球队: {team_name}\n最近 {len(recent)} 场比赛:"]
        for m in recent:
            is_home = name_lower in m.home_team.lower() or m.home_team.lower() in name_lower
            if is_home:
                result_str = "胜" if m.home_goals > m.away_goals else ("平" if m.home_goals == m.away_goals else "负")
                score = f"{m.home_goals}-{m.away_goals}"
                opponent = m.away_team
                if m.home_goals > m.away_goals:
                    wins += 1
                elif m.home_goals == m.away_goals:
                    draws += 1
                else:
                    losses += 1
            else:
                result_str = "胜" if m.away_goals > m.home_goals else ("平" if m.home_goals == m.away_goals else "负")
                score = f"{m.away_goals}-{m.home_goals}"
                opponent = m.home_team
                if m.away_goals > m.home_goals:
                    wins += 1
                elif m.home_goals == m.away_goals:
                    draws += 1
                else:
                    losses += 1

            lines.append(f"  {m.date} [{m.stage}] {m.home_team} {m.home_goals}-{m.away_goals} {m.away_team} → {result_str}")

        lines.append(f"\n战绩统计: {wins}胜 {draws}平 {losses}负")
        return "\n".join(lines)

    def _tool_get_h2h_record(self, args: dict) -> str:
        """get_h2h_record: 查找两队历史交锋。"""
        team_a = args.get("team_a", "").lower()
        team_b = args.get("team_b", "").lower()

        matches = []
        for m in BUILTIN_HISTORICAL_MATCHES:
            home = m.home_team.lower()
            away = m.away_team.lower()
            if ((team_a in home or home in team_a) and (team_b in away or away in team_b)) or \
               ((team_b in home or home in team_b) and (team_a in away or away in team_a)):
                matches.append(m)

        if not matches:
            return f"未找到 {args.get('team_a')} 与 {args.get('team_b')} 的历史交锋记录。"

        a_wins, b_wins, draws = 0, 0, 0
        lines = [f"历史交锋（共 {len(matches)} 场）:"]
        for m in matches:
            if m.home_goals > m.away_goals:
                if m.home_team.lower() in team_a or team_a in m.home_team.lower():
                    a_wins += 1
                else:
                    b_wins += 1
            elif m.home_goals < m.away_goals:
                if m.away_team.lower() in team_a or team_a in m.away_team.lower():
                    a_wins += 1
                else:
                    b_wins += 1
            else:
                draws += 1
            lines.append(f"  {m.date} [{m.tournament} {m.stage}] {m.home_team} {m.home_goals}-{m.away_goals} {m.away_team}")

        lines.append(f"\n统计: {args.get('team_a')} {a_wins}胜 {draws}平 {b_wins}胜 {args.get('team_b')}")
        return "\n".join(lines)

    def _tool_get_poisson_prediction(self, args: dict) -> str:
        """get_poisson_prediction: 泊松模型预测。"""
        home = args.get("home_team", "")
        away = args.get("away_team", "")

        # 从内置排名获取近似 ELO
        home_elo = self._lookup_elo(home)
        away_elo = self._lookup_elo(away)

        pred = self.poisson_predictor.predict_score(home, away, home_elo, away_elo)
        return (
            f"泊松模型预测: {home} vs {away}\n"
            f"最可能比分: {pred.most_likely_score}\n"
            f"主队胜率: {pred.home_win_prob:.1%}\n"
            f"平局概率: {pred.draw_prob:.1%}\n"
            f"客队胜率: {pred.away_win_prob:.1%}\n"
            f"主队预期进球: {pred.home_expected_goals:.2f}\n"
            f"客队预期进球: {pred.away_expected_goals:.2f}\n"
            f"（注: 纯统计模型，不考虑伤病等动态因素）"
        )

    async def _tool_get_team_events(self, args: dict, db: AsyncSession) -> str:
        """get_team_events: 查询球队伤病/换帅等动态事件。"""
        team_name = args.get("team_name", "")
        injector = EventInjector(db)

        # 先尝试精确匹配 fifa_code
        result = await db.execute(
            select(Team).where(Team.name.ilike(f"%{team_name}%"))
        )
        team = result.scalars().first()
        if not team:
            return f"未找到球队: {team_name}，无法查询事件。"

        report = await injector.get_team_events(team.fifa_code)
        if report is None:
            return f"{team_name}: 数据库中无此球队记录。"

        return injector.format_for_agent(report)

    async def _tool_get_group_standings(self, args: dict, db: AsyncSession) -> str:
        """get_group_standings: 查询小组积分排名。"""
        group = args.get("group", "").upper()
        if not group or group not in "ABCDEFGHIJKL":
            return f"无效的小组: {group}，请传入 A-L 之间的字母。"

        result = await db.execute(
            select(Team).where(Team.group_name == group).order_by(Team.fifa_ranking)
        )
        teams = result.scalars().all()

        if not teams:
            return f"小组 {group} 中暂无球队数据。"

        lines = [f"小组 {group} 积分排名（按 FIFA 排名）:"]
        for i, t in enumerate(teams, 1):
            lines.append(
                f"  {i}. {t.name} ({t.name_cn}) — "
                f"FIFA 排名: {t.fifa_ranking or 'N/A'}, "
                f"ELO: {t.elo_rating or 1500:.0f}, "
                f"档次: {t.pot or 'N/A'}"
            )
        return "\n".join(lines)

    # ── 辅助方法 ──────────────────────────────────────────

    def _lookup_elo(self, team_name: str) -> float:
        """从内置数据中查找球队 ELO（近似值）。"""
        # 简单的 FIFA 排名 → ELO 映射
        name_lower = team_name.lower()
        for r in BUILTIN_FIFA_RANKINGS:
            if r.fifa_code.lower() in name_lower or name_lower in r.fifa_code.lower():
                # 基于 FIFA 积分估算 ELO（1000-2200 范围）
                return 1000 + (r.points / 2100) * 1200
        return 1500.0  # 默认

    async def _build_match_context(
        self,
        home_team: str,
        away_team: str,
        db: AsyncSession,
    ) -> str:
        """构建比赛上下文消息。"""
        # 查询两队基本信息
        home_result = await db.execute(
            select(Team).where(Team.name.ilike(f"%{home_team}%"))
        )
        away_result = await db.execute(
            select(Team).where(Team.name.ilike(f"%{away_team}%"))
        )
        home = home_result.scalars().first()
        away = away_result.scalars().first()

        parts = [f"请预测以下比赛的结果：\n"]
        parts.append(f"**主队**: {home_team}")
        if home:
            parts.append(f"  - ELO: {home.elo_rating or 'N/A'}, FIFA排名: {home.fifa_ranking or 'N/A'}, 小组: {home.group_name or 'N/A'}")

        parts.append(f"\n**客队**: {away_team}")
        if away:
            parts.append(f"  - ELO: {away.elo_rating or 'N/A'}, FIFA排名: {away.fifa_ranking or 'N/A'}, 小组: {away.group_name or 'N/A'}")

        parts.append("\n请按照决策流程进行分析，最后调用 submit_prediction 提交你的预测。")
        return "\n".join(parts)

    def _submit_prediction_tool_def(self) -> dict:
        """submit_prediction 工具定义（不注册在 ToolRegistry 中，仅内部使用）。"""
        return {
            "type": "function",
            "function": {
                "name": "submit_prediction",
                "description": (
                    "提交你的最终预测结果。分析完成后必须调用此工具。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "winner": {
                            "type": "string",
                            "description": "胜出球队英文名，或 'draw' 表示平局",
                        },
                        "predicted_score": {
                            "type": "string",
                            "description": "预测比分，如 '2-1'",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "置信度，0 到 1 之间",
                        },
                        "key_factors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "3-5 个关键因素，中文描述",
                        },
                        "reasoning_chain": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "step_number": {"type": "integer"},
                                    "tool_used": {"type": "string"},
                                    "finding": {"type": "string"},
                                    "analysis": {"type": "string"},
                                },
                                "required": ["step_number", "finding"],
                            },
                            "description": "推理步骤链",
                        },
                    },
                    "required": ["winner", "predicted_score", "confidence", "key_factors", "reasoning_chain"],
                },
            },
        }

    def _try_parse_prediction_from_text(self, text: str) -> Optional[dict]:
        """尝试从 Qwen 的文本回复中解析预测数据（最后兜底）。"""
        try:
            # 尝试找 JSON 块
            if "{" in text and "}" in text:
                start = text.index("{")
                end = text.rindex("}") + 1
                json_str = text[start:end]
                data = json.loads(json_str)
                if "winner" in data:
                    return data
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _fallback_to_poisson(self, home_team: str, away_team: str) -> ValidationResult:
        """泊松统计兜底预测。

        当 Agent 不可用时（熔断/校验失败/异常），使用此方法。

        Returns:
            ValidationResult（is_agent=False, model_used="poisson"）。
        """
        logger.info("泊松兜底: %s vs %s", home_team, away_team)

        home_elo = self._lookup_elo(home_team)
        away_elo = self._lookup_elo(away_team)
        pred = self.poisson_predictor.predict_score(home_team, away_team, home_elo, away_elo)

        # 根据概率确定 winner
        if pred.home_win_prob > pred.away_win_prob and pred.home_win_prob > pred.draw_prob:
            winner = home_team
        elif pred.away_win_prob > pred.home_win_prob and pred.away_win_prob > pred.draw_prob:
            winner = away_team
        else:
            winner = "draw"

        confidence = max(pred.home_win_prob, pred.draw_prob, pred.away_win_prob)

        # 构造符合 schema 的预测数据
        prediction_data = {
            "winner": winner,
            "predicted_score": pred.most_likely_score,
            "confidence": round(confidence, 4),
            "key_factors": [
                f"泊松统计模型预测（ELO: {home_team}={home_elo:.0f}, {away_team}={away_elo:.0f}）",
                f"主队胜率 {pred.home_win_prob:.1%}，平局 {pred.draw_prob:.1%}，客队 {pred.away_win_prob:.1%}",
                f"预期进球: {home_team} {pred.home_expected_goals:.2f}, {away_team} {pred.away_expected_goals:.2f}",
            ],
            "reasoning_chain": [
                {"step_number": 1, "tool_used": "poisson_model",
                 "finding": f"泊松模型预测最可能比分 {pred.most_likely_score}",
                 "analysis": f"基于 ELO 推导的攻防指标计算"},
            ],
            "tool_calls_log": [],
        }

        input_data = PredictionInput(**prediction_data)
        validation = validate_prediction(input_data)

        # 覆盖标记为非 Agent 预测
        if validation.is_valid:
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=validation.warnings + ["泊松统计兜底预测（非 Agent）"],
                cleaned_data=validation.cleaned_data,
                model_used="poisson",
                is_agent=False,
            )
        else:
            # 极端情况：连泊松都校验失败
            return ValidationResult(
                is_valid=False,
                errors=validation.errors + ["泊松兜底也校验失败"],
                warnings=validation.warnings,
                cleaned_data=None,
                model_used="poisson",
                is_agent=False,
            )
