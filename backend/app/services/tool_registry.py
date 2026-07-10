"""
Tool Registry — Agent 工具注册表

将 7 个分析工具注册为 DashScope Function Calling 兼容的 JSON Schema 格式，
供 Qwen Agent 在对话中自主调用。

输出格式：
  [
    {
      "type": "function",
      "function": {
        "name": "...",
        "description": "...",
        "parameters": { "type": "object", "properties": {...}, "required": [...] }
      }
    },
    ...
  ]

7 个工具：
  1. get_elo_rating      — ELO 评分
  2. get_fifa_ranking    — FIFA 排名
  3. get_recent_form     — 近期状态
  4. get_h2h_record      — 历史交锋
  5. get_poisson_prediction — 泊松模型预测
  6. get_team_events     — 伤病/换帅事件
  7. get_group_standings — 小组积分
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── 工具数据类 ────────────────────────────────────────────

@dataclass
class Tool:
    """单个 Function Calling 工具定义。"""

    name: str
    description: str
    parameters: dict  # JSON Schema: {"type": "object", "properties": {...}, "required": [...]}

    def to_dashscope_format(self) -> dict:
        """转换为 DashScope Function Calling 的 tools 参数格式。

        Returns:
            {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ── 工具注册表 ────────────────────────────────────────────

class ToolRegistry:
    """Agent 工具注册表。

    管理所有可供 Qwen 调用的分析工具，并提供 DashScope 兼容的输出格式。

    Usage:
        registry = ToolRegistry()
        tools = registry.get_tools()           # → list[dict]，传入 Qwen API
        tool = registry.get_tool_by_name("get_elo_rating")
    """

    def __init__(self) -> None:
        self._tools: list[Tool] = []
        self._tool_map: dict[str, Tool] = {}
        self.register_all()

    # ── 注册 ─────────────────────────────────────────────

    def _register(self, tool: Tool) -> None:
        """内部注册方法。"""
        self._tools.append(tool)
        self._tool_map[tool.name] = tool
        logger.debug("注册工具: %s", tool.name)

    def register_all(self) -> None:
        """注册全部 7 个分析工具。"""

        # ── 1. get_elo_rating ──
        self._register(Tool(
            name="get_elo_rating",
            description=(
                "获取指定球队的当前 ELO 评分。ELO 评分反映球队综合实力，"
                "数值越高实力越强（顶级球队通常在 1900-2100 之间）。"
                "可用于评估两队实力差距、预测比赛胜负概率。"
                "当你需要了解一支球队的实力水平时，优先调用此工具。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "team_name": {
                        "type": "string",
                        "description": "球队英文名，如 'Argentina'、'Brazil'、'Japan'",
                    },
                },
                "required": ["team_name"],
            },
        ))

        # ── 2. get_fifa_ranking ──
        self._register(Tool(
            name="get_fifa_ranking",
            description=(
                "获取指定球队的最新 FIFA 世界排名及积分。"
                "FIFA 排名是国际足联官方发布的球队排名，每月更新。"
                "排名数值越小越好（第 1 名最强），积分越高越好。"
                "可与 ELO 评分结合使用，从不同维度评估球队实力。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "team_name": {
                        "type": "string",
                        "description": "球队英文名，如 'France'、'Germany'、'Korea Republic'",
                    },
                },
                "required": ["team_name"],
            },
        ))

        # ── 3. get_recent_form ──
        self._register(Tool(
            name="get_recent_form",
            description=(
                "获取指定球队最近 N 场比赛的战绩记录，包括比分、赛事类型和日期。"
                "近期状态是判断球队当前竞技水平的重要依据。"
                "可用于分析球队是否处于上升期或低迷期，以及主客场表现差异。"
                "默认返回最近 10 场比赛。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "team_name": {
                        "type": "string",
                        "description": "球队英文名，如 'Spain'、'England'",
                    },
                    "n_matches": {
                        "type": "integer",
                        "description": "查询最近几场比赛，默认 10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["team_name"],
            },
        ))

        # ── 4. get_h2h_record ──
        self._register(Tool(
            name="get_h2h_record",
            description=(
                "获取两支球队的历史交锋记录，包括总场次、胜负平统计和关键比赛详情。"
                "历史交锋数据可以揭示球队之间的'克星'关系和心理优势。"
                "某些球队虽然整体实力不如对手，但在直接对话中表现优异。"
                "预测两队比赛时，务必查看交锋记录。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "team_a": {
                        "type": "string",
                        "description": "球队 A 的英文名，如 'Argentina'",
                    },
                    "team_b": {
                        "type": "string",
                        "description": "球队 B 的英文名，如 'France'",
                    },
                },
                "required": ["team_a", "team_b"],
            },
        ))

        # ── 5. get_poisson_prediction ──
        self._register(Tool(
            name="get_poisson_prediction",
            description=(
                "使用泊松分布统计模型预测两队比赛的比分和胜负概率。"
                "基于两队的 ELO 评分推导攻击力和防守力，计算预期进球数，"
                "返回最可能比分、主队胜率、平局概率和客队胜率。"
                "这是纯数学模型的预测结果，可作为你综合分析的参考基线。"
                "注意：泊松模型不考虑伤病、士气等动态因素。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "home_team": {
                        "type": "string",
                        "description": "主队英文名，如 'Brazil'",
                    },
                    "away_team": {
                        "type": "string",
                        "description": "客队英文名，如 'Germany'",
                    },
                },
                "required": ["home_team", "away_team"],
            },
        ))

        # ── 6. get_team_events ──
        self._register(Tool(
            name="get_team_events",
            description=(
                "获取指定球队当前活跃的动态事件，包括伤病、换帅、战术变化、士气波动等。"
                "这些动态因素可能显著影响球队表现，是纯统计模型无法捕捉的信息。"
                "事件有严重程度分级（CRITICAL/MAJOR/MINOR），"
                "CRITICAL 级别的事件（如核心球员重伤）可能使球队实力下降 10-20%。"
                "预测前务必查看相关球队的最新事件。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "team_name": {
                        "type": "string",
                        "description": "球队英文名，如 'Portugal'、'Morocco'",
                    },
                },
                "required": ["team_name"],
            },
        ))

        # ── 7. get_group_standings ──
        self._register(Tool(
            name="get_group_standings",
            description=(
                "获取指定小组（A-L）的积分排名表。"
                "小组赛阶段每队打 3 场比赛，前两名晋级淘汰赛。"
                "积分规则：胜 3 分、平 1 分、负 0 分。"
                "积分相同时依次比较净胜球、进球数、交锋记录。"
                "可用于分析小组出线形势和淘汰赛对阵可能性。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "group": {
                        "type": "string",
                        "description": "小组字母，A 到 L，如 'A'、'F'",
                        "enum": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"],
                    },
                },
                "required": ["group"],
            },
        ))

        logger.info("工具注册完成，共 %d 个工具", len(self._tools))

    # ── 查询 ─────────────────────────────────────────────

    def get_tools(self) -> list[dict]:
        """返回全部工具的 DashScope Function Calling 格式列表。

        可直接作为 Qwen API 请求的 tools 参数传入。

        Returns:
            [{"type": "function", "function": {...}}, ...]
        """
        return [tool.to_dashscope_format() for tool in self._tools]

    def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """按名称查找工具。

        Args:
            name: 工具名称，如 'get_elo_rating'。

        Returns:
            Tool 实例，未找到返回 None。
        """
        return self._tool_map.get(name)

    def get_tool_names(self) -> list[str]:
        """返回所有已注册工具的名称列表。"""
        return [tool.name for tool in self._tools]

    @property
    def tool_count(self) -> int:
        """已注册工具数量。"""
        return len(self._tools)
