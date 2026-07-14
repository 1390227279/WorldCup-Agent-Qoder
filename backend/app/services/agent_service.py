"""Qwen orchestration for explaining immutable simulated match results."""

from __future__ import annotations

import json
import time
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.historical_match import HistoricalMatch
from app.models.data_collection import DataCollectionRun
from app.schema.prediction_schema import (
    AgentReportInput,
    AgentReportValidationResult,
    ToolCallRecord,
    validate_agent_report,
)
from app.services.data_collector import (
    BUILTIN_FIFA_RANKINGS,
)
from app.services.elo_engine import elo_to_win_probability, normalize_elo
from app.services.qwen_client import QwenClient
from app.services.tool_registry import ToolRegistry


SIMULATED_MATCH_ANALYSIS_PROMPT = """你是一位足球战术分析员，负责解释已经由数学引擎确定的比赛推演结果。

不可违反的约束：
- 所有面向用户的输出必须使用简体中文，包括关键因素、风险提示、推理发现和分析文字。
- 即使球队英文名、工具数据或历史比赛使用英文，也必须用中文组织结论；球队优先使用中文名称。
- 输入中的球队、比分、胜者、胜率和预期进球 lambda 均为后端数学事实。
- 不得重新预测、修改、纠正或否定这些数学事实。
- 只能解释战术原因、关键因素和不确定性。
- “数学影响事件”已经进入胜率模型；“叙事背景事件”只用于解释，不得声称其改变了比分或概率。
- 不得补充未出现在数学影响事件或叙事背景事件中的伤病、换帅或其他事件。
- 工具结果若与数学上下文不同，仍以数学上下文为准。

请给出 3-5 个关键因素、风险提示和连续推理步骤，最后调用 submit_match_analysis。
"""

TOURNAMENT_REPORT_PROMPT = """你是世界杯冠军推演报告撰稿人。输入 JSON 是后端数学引擎已经确定的只读事实。
必须使用简体中文。不得修改冠军、比分、晋级球队、概率、事件分类或模拟路径。
数学影响事件已经进入概率模型；叙事背景事件只用于解释，禁止声称其改变了胜率。
请覆盖小组赛晋级、五轮淘汰赛、决赛、关键因素、事件影响、替代结果和模型风险。
最后必须调用 submit_tournament_report，推理步骤必须连续且从 1 开始。"""

MAX_ROUNDS = 5
ALLOWED_TOOL_NAMES = {
    "get_elo_rating",
    "get_fifa_ranking",
    "get_recent_form",
    "get_h2h_record",
}


class AgentService:
    def __init__(
        self,
        qwen_client: Optional[QwenClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ) -> None:
        self.qwen_client = qwen_client or QwenClient()
        self.tool_registry = tool_registry or ToolRegistry()

    async def analyze_simulated_match(
        self,
        match_context: dict,
        db_session: AsyncSession,
    ) -> AgentReportValidationResult:
        home_team = (
            match_context["home_team"].get("name_cn")
            or match_context["home_team"]["name"]
        )
        away_team = (
            match_context["away_team"].get("name_cn")
            or match_context["away_team"]["name"]
        )
        messages = [
            {"role": "system", "content": SIMULATED_MATCH_ANALYSIS_PROMPT},
            {
                "role": "user",
                "content": (
                    f"请解释 {home_team} 对阵 {away_team} 的既有数学推演。\n"
                    "以下 JSON 是不可修改的权威上下文：\n"
                    f"```json\n{json.dumps(match_context, ensure_ascii=False, indent=2)}\n```"
                ),
            },
        ]
        tools = [
            tool
            for tool in self.tool_registry.get_tools()
            if tool["function"]["name"] in ALLOWED_TOOL_NAMES
        ]
        tools.append(self._submit_match_analysis_tool_def())

        report_data: Optional[dict] = None
        tool_records: list[ToolCallRecord] = []
        for _round_num in range(MAX_ROUNDS):
            response = await self.qwen_client.chat_with_tools(messages, tools)
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    if tool_call.name == "submit_match_analysis":
                        report_data = tool_call.arguments
                        break
                    started_at = int(time.time() * 1000)
                    tool_result = await self._execute_tool(
                        tool_call.name,
                        tool_call.arguments,
                        db_session,
                    )
                    tool_records.append(ToolCallRecord(
                        tool_name=tool_call.name,
                        input_params=tool_call.arguments,
                        output_summary=tool_result[:500],
                        execution_time_ms=int(time.time() * 1000) - started_at,
                        success=not tool_result.startswith("工具执行出错"),
                    ))
                    messages.extend([
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.name,
                                    "arguments": json.dumps(
                                        tool_call.arguments,
                                        ensure_ascii=False,
                                    ),
                                },
                            }],
                        },
                        {
                            "role": "tool",
                            "content": tool_result,
                            "tool_call_id": tool_call.id,
                        },
                    ])
                if report_data is not None:
                    break
                continue
            if response.content:
                report_data = self._try_parse_report_from_text(response.content)
            break

        if report_data is None:
            return AgentReportValidationResult(
                is_valid=False,
                errors=["智能分析未提交解释报告"],
            )
        report_data["tool_calls_log"] = [
            record.model_dump() for record in tool_records
        ]
        return validate_agent_report(AgentReportInput(**report_data))

    async def analyze_tournament(self, context: dict) -> dict:
        messages = [
            {"role": "system", "content": TOURNAMENT_REPORT_PROMPT},
            {"role": "user", "content": "请解释这份冠军推演：\n" + json.dumps(context, ensure_ascii=False)},
        ]
        response = await self.qwen_client.chat_with_tools(
            messages,
            [self._submit_tournament_report_tool_def()],
        )
        report = next(
            (call.arguments for call in response.tool_calls if call.name == "submit_tournament_report"),
            None,
        )
        if report is None and response.content:
            report = self._try_parse_report_from_text(response.content)
        if not isinstance(report, dict):
            raise ValueError("Qwen 未提交冠军推演报告")
        if any(not str(report.get(field, "")).strip() for field in ("champion_summary", "final_reasoning")):
            raise ValueError("冠军推演报告缺少必要结论")
        for field in (
            "group_stage_reasoning", "knockout_reasoning", "key_factors",
            "event_analysis", "alternative_outcomes", "risk_notes",
        ):
            report[field] = [str(item).strip() for item in report.get(field, []) if str(item).strip()][:12]
        chain = []
        for item in report.get("reasoning_chain", []):
            if not isinstance(item, dict) or not str(item.get("finding", "")).strip():
                continue
            chain.append({
                "step_number": len(chain) + 1,
                "tool_used": item.get("tool_used"),
                "finding": str(item["finding"]).strip(),
                "analysis": str(item.get("analysis", "")).strip() or None,
            })
        report["reasoning_chain"] = chain
        return report

    @staticmethod
    def _submit_tournament_report_tool_def() -> dict:
        list_property = {"type": "array", "items": {"type": "string"}}
        return {
            "type": "function",
            "function": {
                "name": "submit_tournament_report",
                "description": "提交中文世界杯冠军完整推演报告",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "champion_summary": {"type": "string"},
                        "group_stage_reasoning": list_property,
                        "knockout_reasoning": list_property,
                        "final_reasoning": {"type": "string"},
                        "key_factors": list_property,
                        "event_analysis": list_property,
                        "alternative_outcomes": list_property,
                        "risk_notes": list_property,
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
                                "required": ["finding"],
                            },
                        },
                    },
                    "required": [
                        "champion_summary", "group_stage_reasoning", "knockout_reasoning",
                        "final_reasoning", "key_factors", "event_analysis",
                        "alternative_outcomes", "risk_notes", "reasoning_chain",
                    ],
                },
            },
        }

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        db_session: AsyncSession,
    ) -> str:
        try:
            if tool_name == "get_elo_rating":
                return await self._tool_get_elo_rating(arguments, db_session)
            if tool_name == "get_fifa_ranking":
                return await self._tool_get_fifa_ranking(arguments, db_session)
            if tool_name == "get_recent_form":
                return await self._tool_get_recent_form(arguments, db_session)
            if tool_name == "get_h2h_record":
                return await self._tool_get_h2h_record(arguments, db_session)
            return f"当前分析不允许调用工具：{tool_name}"
        except Exception as exc:
            return f"工具执行出错：{exc}"

    @staticmethod
    async def _find_team(team_name: str, db: AsyncSession) -> Team | None:
        result = await db.execute(
            select(Team).where(or_(
                Team.name.ilike(f"%{team_name}%"),
                Team.name_cn.ilike(f"%{team_name}%"),
                Team.fifa_code.ilike(team_name),
            ))
        )
        return result.scalars().first()

    async def _tool_get_elo_rating(self, args: dict, db: AsyncSession) -> str:
        team = await self._find_team(args.get("team_name", ""), db)
        if not team:
            return f"未找到球队：{args.get('team_name', '')}"
        elo = team.elo_rating or 1500.0
        return (
            f"球队：{team.name}（{team.name_cn}）\n"
            f"ELO 评分：{elo:.0f}\n"
            f"标准化评分：{normalize_elo(elo):.1f}/100\n"
            f"对阵平均实力球队胜率：{elo_to_win_probability(elo, 1500.0):.1%}\n"
            f"足联：{team.confederation}"
        )

    async def _tool_get_fifa_ranking(self, args: dict, db: AsyncSession) -> str:
        team_name = args.get("team_name", "")
        team = await self._find_team(team_name, db)
        if not team:
            return f"未找到球队：{team_name}"
        points = next(
            (
                ranking.points
                for ranking in BUILTIN_FIFA_RANKINGS
                if ranking.fifa_code == team.fifa_code
            ),
            0.0,
        )
        return (
            f"球队：{team.name}（{team.name_cn}）\n"
            f"FIFA 排名：第 {team.fifa_ranking or '未知'} 名\n"
            f"FIFA 积分：{points:.0f}\n"
            f"足联：{team.confederation}"
        )

    async def _tool_get_recent_form(self, args: dict, db: AsyncSession) -> str:
        team = await self._find_team(args.get("team_name", ""), db)
        if not team: return f"未找到球队：{args.get('team_name', '')}"
        limit = max(1, min(int(args.get("n_matches", 10)), 20))
        matches = list((await db.execute(select(HistoricalMatch).where(or_(
            HistoricalMatch.home_team_id == team.id, HistoricalMatch.away_team_id == team.id,
        )).order_by(HistoricalMatch.match_date.desc()).limit(limit))).scalars())
        if not matches: return f"暂无 {team.name_cn} 的已采集历史比赛；未使用硬编码数据替代。"
        return await self._format_history(f"{team.name_cn} 最近 {len(matches)} 场已采集比赛：", matches, db)

    async def _tool_get_h2h_record(self, args: dict, db: AsyncSession) -> str:
        team_a = await self._find_team(args.get("team_a", ""), db); team_b = await self._find_team(args.get("team_b", ""), db)
        if not team_a or not team_b: return "无法匹配历史交锋查询中的球队"
        matches = list((await db.execute(select(HistoricalMatch).where(or_(
            and_(HistoricalMatch.home_team_id == team_a.id, HistoricalMatch.away_team_id == team_b.id),
            and_(HistoricalMatch.home_team_id == team_b.id, HistoricalMatch.away_team_id == team_a.id),
        )).order_by(HistoricalMatch.match_date.desc()).limit(20))).scalars())
        if not matches: return f"暂无 {team_a.name_cn} 与 {team_b.name_cn} 的已采集历史交锋；未使用硬编码数据替代。"
        return await self._format_history(f"{team_a.name_cn} 与 {team_b.name_cn} 已采集交锋共 {len(matches)} 场：", matches, db)

    @staticmethod
    async def _format_history(title: str, matches: list[HistoricalMatch], db: AsyncSession) -> str:
        run_ids = {match.source_run_id for match in matches}
        runs = list((await db.execute(select(DataCollectionRun).where(DataCollectionRun.id.in_(run_ids)))).scalars())
        evidence = ", ".join(f"#{run.id} {run.source_name} {run.sha256_hash[:8] if run.sha256_hash else '无哈希'}" for run in runs)
        lines = [title]
        lines.extend(f"{m.match_date.isoformat()} [{m.tournament} {m.stage}] {m.home_fifa_code} {m.home_goals}-{m.away_goals} {m.away_fifa_code}" for m in matches)
        lines.append(f"数据证据：{evidence}")
        return "\n".join(lines)

    @staticmethod
    def _submit_match_analysis_tool_def() -> dict:
        return {
            "type": "function",
            "function": {
                "name": "submit_match_analysis",
                "description": "提交对数学推演结果的解释，不得提交比分、胜者、概率或 lambda。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key_factors": {
                            "type": "array",
                            "description": "3-5 条简体中文关键因素",
                            "items": {
                                "type": "string",
                                "description": "必须使用简体中文",
                            },
                        },
                        "risk_notes": {
                            "type": "array",
                            "description": "简体中文风险与边界说明",
                            "items": {
                                "type": "string",
                                "description": "必须使用简体中文",
                            },
                        },
                        "reasoning_chain": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "step_number": {"type": "integer"},
                                    "tool_used": {"type": "string"},
                                    "finding": {
                                        "type": "string",
                                        "description": "必须使用简体中文",
                                    },
                                    "analysis": {
                                        "type": "string",
                                        "description": "必须使用简体中文",
                                    },
                                },
                                "required": ["step_number", "finding"],
                            },
                        },
                    },
                    "required": ["key_factors", "risk_notes", "reasoning_chain"],
                },
            },
        }

    @staticmethod
    def _try_parse_report_from_text(text: str) -> Optional[dict]:
        try:
            if "{" in text and "}" in text:
                data = json.loads(text[text.index("{"):text.rindex("}") + 1])
                if "key_factors" in data:
                    return data
        except (json.JSONDecodeError, ValueError):
            pass
        return None
