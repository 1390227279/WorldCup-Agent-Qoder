"""Bracket API routes — Phase 3 实现。

提供对阵树结构和单队晋级路径查询。
"""

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import get_db
from app.models.match import Match
from app.models.team import Team
from app.services.monte_carlo import get_engine

logger = logging.getLogger(__name__)

router = APIRouter()


# ── 淘汰赛阶段定义（用于组装树结构） ─────────────────────
KNOCKOUT_STAGES = ["R32", "R16", "QF", "SF", "THIRD", "FINAL"]
STAGE_ORDER = {s: i for i, s in enumerate(["GROUP", *KNOCKOUT_STAGES])}


# ── 路由 ──────────────────────────────────────────────────

@router.get("")
async def get_bracket(db: AsyncSession = Depends(get_db)):
    """返回完整对阵树结构。

    从数据库读取所有 Match 记录，按 stage 分组，
    构建前端可直接渲染的树形 JSON。

    Response:
        {
            "stages": {
                "GROUP": { "label": "小组赛", "matches": [...] },
                "R32":   { "label": "32 强",  "matches": [...] },
                ...
            },
            "total_matches": 104
        }
    """
    result = await db.execute(
        select(Match)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
        )
        .order_by(Match.stage, Match.match_order, Match.id)
    )
    matches = result.scalars().all()

    # 阶段标签映射
    stage_labels = {
        "GROUP": "小组赛",
        "R32": "32 强",
        "R16": "16 强",
        "QF": "1/4 决赛",
        "SF": "半决赛",
        "THIRD": "三四名决赛",
        "FINAL": "决赛",
    }

    # 按 stage 分组
    stages: dict[str, list] = defaultdict(list)
    for m in matches:
        match_data = {
            "id": m.id,
            "stage": m.stage,
            "round_name": m.round_name,
            "home_team": m.home_team.to_dict() if m.home_team else None,
            "away_team": m.away_team.to_dict() if m.away_team else None,
            "home_score": m.home_score,
            "away_score": m.away_score,
            "is_simulated": m.is_simulated,
            "match_order": m.match_order,
        }
        stages[m.stage].append(match_data)

    # 组装输出（按阶段顺序排列）
    ordered_stages = {}
    for stage in ["GROUP", *KNOCKOUT_STAGES]:
        if stage in stages:
            ordered_stages[stage] = {
                "label": stage_labels.get(stage, stage),
                "matches": stages[stage],
            }

    return {
        "stages": ordered_stages,
        "total_matches": len(matches),
    }


@router.get("/team/{team_id}")
async def get_team_bracket_path(
    team_id: int,
    db: AsyncSession = Depends(get_db),
):
    """返回某队的淘汰赛晋级路径（潜在对手）。

    查询逻辑：
      1. 找到该队参加的所有淘汰赛 Match
      2. 对每场比赛，标注对手信息和比赛结果
      3. 返回按阶段排序的晋级路径

    Response:
        {
            "team": { ... },
            "knockout_path": [
                {
                    "stage": "R32",
                    "round_name": "...",
                    "opponent": { ... } | null,
                    "result": "W" | "L" | "D" | null,
                    "score": "2-1" | null,
                    "match_id": 50,
                },
                ...
            ]
        }
    """
    # 查询球队
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail=f"球队 ID={team_id} 不存在")

    # 查询该队参加的所有淘汰赛 Match
    result = await db.execute(
        select(Match)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
        )
        .where(
            (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
            Match.stage.in_(KNOCKOUT_STAGES),
        )
        .order_by(Match.stage, Match.match_order, Match.id)
    )
    matches = result.scalars().all()

    # 构建晋级路径
    knockout_path = []
    for m in matches:
        # 判断该队是主队还是客队
        is_home = m.home_team_id == team_id
        opponent = m.away_team if is_home else m.home_team

        # 判断胜负
        result_flag = None
        score_str = None
        if m.home_score is not None and m.away_score is not None:
            score_str = f"{m.home_score}-{m.away_score}"
            my_score = m.home_score if is_home else m.away_score
            opp_score = m.away_score if is_home else m.home_score
            if my_score > opp_score:
                result_flag = "W"
            elif my_score < opp_score:
                result_flag = "L"
            else:
                result_flag = "D"

        knockout_path.append({
            "stage": m.stage,
            "round_name": m.round_name,
            "opponent": opponent.to_dict() if opponent else None,
            "result": result_flag,
            "score": score_str,
            "match_id": m.id,
        })

    # 按阶段顺序排序
    knockout_path.sort(key=lambda x: STAGE_ORDER.get(x["stage"], 99))

    return {
        "team": team.to_dict(),
        "knockout_path": knockout_path,
    }


@router.get("/simulation")
async def get_simulation_results(
    iterations: int = Query(1000, ge=100, le=10000, description="模拟次数"),
    refresh: bool = Query(False, description="强制重新计算（忽略缓存）"),
    event_ids: str = Query("", description="逗号分隔的事件ID"),
    db: AsyncSession = Depends(get_db),
):
    """运行 Monte Carlo 模拟，返回夺冠概率。"""
    # 1. 获取所有球队
    teams_result = await db.execute(select(Team))
    teams = teams_result.scalars().all()
    if not teams:
        return {"error": "No teams available"}

    # 2. 处理事件影响
    team_impacts = None
    if event_ids:
        from app.models.event import Event
        ids = [int(x.strip()) for x in event_ids.split(",") if x.strip().isdigit()]
        if ids:
            events_result = await db.execute(
                select(Event).where(Event.id.in_(ids), Event.active == True)
            )
            events = events_result.scalars().all()
            impact_map: dict = defaultdict(lambda: {"attack": 0.0, "defense": 0.0})
            for ev in events:
                if ev.team and ev.impact:
                    code = ev.team.fifa_code
                    for key, val in ev.impact.items():
                        if isinstance(val, (int, float)):
                            impact_map[code][key] = impact_map[code].get(key, 0.0) + val
            team_impacts = dict(impact_map)

    # 3. 构建球队数据
    teams_data = []
    for t in teams:
        teams_data.append({
            "id": t.id,
            "name": t.name,
            "name_cn": t.name_cn,
            "fifa_code": t.fifa_code,
            "elo_rating": t.elo_rating,
            "group_name": t.group_name,
        })

    # 4. 运行模拟
    engine = get_engine()
    result = engine.run(teams_data, iterations=iterations,
                        force_refresh=refresh, team_impacts=team_impacts)
    return result
