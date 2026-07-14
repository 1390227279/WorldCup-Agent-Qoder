"""Bracket API routes — Phase 3 实现。

提供对阵树结构和单队晋级路径查询。
"""

import copy
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.team import Team
from app.models.tournament import DEFAULT_TOURNAMENT_CODE, Tournament, TournamentTeam
from app.schema.simulation_schema import SimulationResponse
from app.services.monte_carlo import get_engine
from app.services.scenario_resolver import ScenarioResolution, resolve_scenario_events
from app.services.simulation_cache import (
    build_simulation_context_key,
    get_simulation_cache,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _scenario_label(scenario_type: str, scenario: ScenarioResolution) -> str:
    if scenario_type == "BASELINE":
        return "基础实力基线（不含事件）"
    if scenario.math_events:
        return "当前事件情景"
    if scenario.narrative_events:
        return "当前 AI 解读上下文（数学基线不变）"
    return "所选事件未应用（数学基线不变）"


def _build_simulation_response(
    *,
    engine_result: dict,
    simulation_id: str,
    baseline_simulation_id: str,
    scenario_type: str,
    scenario: ScenarioResolution,
    tournament: Tournament,
) -> dict:
    audit = scenario.audit_dict()
    response = {
        "simulation_id": simulation_id,
        "baseline_simulation_id": baseline_simulation_id,
        "scenario": {
            "type": scenario_type,
            "label": _scenario_label(scenario_type, scenario),
            **audit,
        },
        "tournament": {
            "id": tournament.id,
            "code": tournament.code,
            "name": tournament.name,
            "name_cn": tournament.name_cn,
            "year": tournament.year,
            "status": tournament.status,
            "data_version": tournament.data_version,
            "rules_version": tournament.rules_version,
            "is_official": tournament.status == "OFFICIAL",
        },
        "model": {
            "version": engine_result["model_version"],
            "iterations": engine_result["iterations"],
            "seed": engine_result["seed"],
            "input_fingerprint": engine_result["input_fingerprint"],
        },
        "summary": {
            "probability_leader": engine_result["probability_leader"],
            "top3": engine_result["top3"],
            "advancement_probs": engine_result["advancement_probs"],
            "champion_probs_by_team_id": engine_result[
                "champion_probs_by_team_id"
            ],
        },
        "representative_path": engine_result["representative_path"],
    }
    return SimulationResponse.model_validate(response).model_dump()


@router.get("/simulation", response_model=SimulationResponse)
async def get_simulation_results(
    iterations: int = Query(1000, ge=100, le=10000, description="模拟次数"),
    seed: int | None = Query(None, ge=1, description="可选的可复现主种子"),
    refresh: bool = Query(False, description="强制重新计算（忽略缓存）"),
    event_ids: str = Query("", description="逗号分隔的事件ID"),
    baseline_simulation_id: str | None = Query(
        None, description="事件情景所依赖的基线模拟ID"
    ),
    db: AsyncSession = Depends(get_db),
):
    """返回稳定的无事件基线或基于指定基线的事件情景。"""
    # 1. 获取当前赛事的活跃参赛球队
    teams_result = await db.execute(
        select(Team, TournamentTeam, Tournament)
        .join(TournamentTeam, TournamentTeam.team_id == Team.id)
        .join(Tournament, Tournament.id == TournamentTeam.tournament_id)
        .where(
            Tournament.code == DEFAULT_TOURNAMENT_CODE,
            TournamentTeam.active.is_(True),
        )
        .order_by(TournamentTeam.group_name, TournamentTeam.pot)
    )
    tournament_teams = teams_result.all()
    if not tournament_teams:
        raise HTTPException(status_code=404, detail="当前赛事没有可用参赛球队")
    tournament = tournament_teams[0][2]

    # 2. 处理事件影响
    scenario = await resolve_scenario_events(db, event_ids)
    team_impacts = scenario.team_impacts or None

    # 3. 构建球队数据
    teams_data = []
    for t, participant, _tournament in tournament_teams:
        teams_data.append({
            "id": t.id,
            "name": t.name,
            "name_cn": t.name_cn,
            "fifa_code": t.fifa_code,
            "confederation": t.confederation,
            "fifa_ranking": t.fifa_ranking,
            "elo_rating": t.elo_rating,
            "tournament_group": participant.group_name,
            "tournament_pot": participant.pot,
            "stats": t.stats,
        })

    context_key = build_simulation_context_key(
        tournament_id=tournament.id,
        tournament_code=tournament.code,
        data_version=tournament.data_version,
        rules_version=tournament.rules_version,
        iterations=iterations,
        teams=teams_data,
    )
    engine = get_engine()
    cache = get_simulation_cache()

    def compute_response(
        *,
        master_seed: int,
        scenario_resolution: ScenarioResolution,
        scenario_type: str,
        baseline_id: str | None = None,
        force: bool = False,
    ) -> dict:
        engine_result = engine.run(
            teams_data,
            iterations=iterations,
            force_refresh=force,
            team_impacts=scenario_resolution.team_impacts or None,
            event_ids=scenario_resolution.requested_event_ids,
            seed=master_seed,
        )
        simulation_id = uuid.uuid4().hex
        return _build_simulation_response(
            engine_result=engine_result,
            simulation_id=simulation_id,
            baseline_simulation_id=baseline_id or simulation_id,
            scenario_type=scenario_type,
            scenario=scenario_resolution,
            tournament=tournament,
        )

    if not scenario.requested_event_ids:
        cached_baseline = None if refresh else cache.get_baseline(context_key, seed)
        if cached_baseline is not None:
            return cached_baseline.response
        master_seed = seed or cache.new_seed()
        response = compute_response(
            master_seed=master_seed,
            scenario_resolution=scenario,
            scenario_type="BASELINE",
            force=refresh,
        )
        cache.store_baseline(context_key, response)
        return response

    baseline_record = None
    if baseline_simulation_id:
        baseline_record = cache.get_by_id(baseline_simulation_id)
        if baseline_record is None:
            raise HTTPException(status_code=404, detail="基线模拟不存在或已过期")
        if baseline_record.scenario_type != "BASELINE":
            raise HTTPException(status_code=400, detail="指定ID不是基线模拟")
        if baseline_record.context_key != context_key:
            raise HTTPException(status_code=400, detail="基线模拟与当前赛事参数不匹配")
        if seed is not None and seed != baseline_record.seed:
            raise HTTPException(status_code=400, detail="显式种子与基线模拟不一致")
    else:
        baseline_record = cache.get_baseline(context_key, seed)

    if baseline_record is None:
        baseline_seed = seed or cache.new_seed()
        baseline_scenario = ScenarioResolution(requested_event_ids=[])
        baseline_response = compute_response(
            master_seed=baseline_seed,
            scenario_resolution=baseline_scenario,
            scenario_type="BASELINE",
        )
        baseline_record = cache.store_baseline(context_key, baseline_response)

    cached_scenario = None if refresh else cache.get_scenario(
        context_key,
        baseline_record.simulation_id,
        scenario.event_content_fingerprint,
    )
    if cached_scenario is not None:
        return cached_scenario.response

    if not scenario.team_impacts:
        response = copy.deepcopy(baseline_record.response)
        response["simulation_id"] = uuid.uuid4().hex
        response["baseline_simulation_id"] = baseline_record.simulation_id
        response["scenario"] = {
            "type": "EVENT",
            "label": _scenario_label("EVENT", scenario),
            **scenario.audit_dict(),
        }
        response = SimulationResponse.model_validate(response).model_dump()
        cache.store_scenario(context_key, response)
        return response

    response = compute_response(
        master_seed=baseline_record.seed,
        scenario_resolution=scenario,
        scenario_type="EVENT",
        baseline_id=baseline_record.simulation_id,
        force=refresh,
    )
    cache.store_scenario(context_key, response)
    return response
