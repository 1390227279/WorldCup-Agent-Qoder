"""
Phase 2-4 API 端点集成测试。

使用 pytest + httpx.AsyncClient 测试 FastAPI 端点。
每个测试使用独立的内存数据库，自动 seed 48 支球队。

Run: pytest tests/test_api.py -v
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from app.main import app
from app.models.database import Base, get_db


@pytest_asyncio.fixture
async def db_session():
    """为每个测试创建独立的内存数据库并 seed 数据。"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.models.seed import seed_all

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        await seed_all(session)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
def reset_prediction_breaker():
    """每个测试前重置预测路由的全局熔断器。"""
    from app.routers.predictions import _get_prediction_service
    from app.services.simulation_cache import get_simulation_cache

    _get_prediction_service().breaker.reset()
    get_simulation_cache().clear()


@pytest_asyncio.fixture
async def client(db_session):
    """httpx.AsyncClient，已注入测试数据库会话。"""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── Tests ─────────────────────────────────────────────────


class TestHealthEndpoint:
    async def test_health_returns_200(self, client):
        """GET /api/v1/health 应返回 200。"""
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "version" in body


class TestTeamsEndpoint:
    async def test_teams_returns_48(self, client):
        """GET /api/v1/teams 应只返回当前赛事的 48 支活跃球队。"""
        resp = await client.get("/api/v1/teams")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 48
        assert len({team["fifa_code"] for team in data}) == 48
        assert {team["tournament"]["status"] for team in data} == {"SCENARIO"}
        assert {
            team["tournament"]["qualification_status"] for team in data
        } == {"SCENARIO"}
        assert all("group_name" not in team and "pot" not in team for team in data)


class TestEventsEndpoint:
    async def test_events_returns_json_array(self, client):
        """GET /api/v1/events 应返回 JSON 数组。"""
        resp = await client.get("/api/v1/events")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_event_crud_invalidates_simulation_cache(self, client):
        initial = await client.get("/api/v1/bracket/simulation?iterations=100")
        initial_id = initial.json()["simulation_id"]

        created = await client.post("/api/v1/events", json={
            "team_id": 1,
            "type": "INJURY",
            "title": "测试伤病事件",
            "severity": "MINOR",
            "impact": {"attack": -0.05},
        })
        assert created.status_code == 200
        assert created.json()["impact"] == {"attack_lambda_delta": -0.05}
        assert created.json()["impact_mode"] == "MATH"
        assert created.json()["affects_probability"] is True
        event_id = created.json()["id"]

        after_create = await client.get("/api/v1/bracket/simulation?iterations=100")
        assert after_create.json()["simulation_id"] == initial_id

        first_scenario = await client.get(
            f"/api/v1/bracket/simulation?iterations=100&event_ids={event_id}"
            f"&baseline_simulation_id={initial_id}"
        )
        first_scenario_id = first_scenario.json()["simulation_id"]

        updated = await client.put(f"/api/v1/events/{event_id}", json={"active": False})
        assert updated.status_code == 200
        assert updated.json()["active"] is False

        second_scenario = await client.get(
            f"/api/v1/bracket/simulation?iterations=100&event_ids={event_id}"
            f"&baseline_simulation_id={initial_id}"
        )
        assert second_scenario.json()["simulation_id"] != first_scenario_id
        assert second_scenario.json()["scenario"]["ignored_events"] == [
            {"event_id": event_id, "reason": "inactive"}
        ]
        assert second_scenario.json()["baseline_simulation_id"] == initial_id

        deleted = await client.delete(f"/api/v1/events/{event_id}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True

    async def test_event_impact_modes_are_explicit_and_validated(self, client):
        narrative = await client.post("/api/v1/events", json={
            "team_id": 1,
            "type": "MORALE",
            "title": "主场叙事背景",
            "severity": "MINOR",
            "impact": {"team_morale": 0.1},
            "impact_mode": "NARRATIVE",
        })
        assert narrative.status_code == 200
        assert narrative.json()["impact_mode"] == "NARRATIVE"
        assert narrative.json()["affects_probability"] is False

        empty_math = await client.post("/api/v1/events", json={
            "team_id": 1,
            "type": "TACTICAL",
            "title": "缺少数学修正",
            "severity": "MINOR",
            "impact": {},
            "impact_mode": "MATH",
        })
        assert empty_math.status_code == 400
        assert "非零进球期望修正" in empty_math.json()["detail"]

        narrative_with_lambda = await client.post("/api/v1/events", json={
            "team_id": 1,
            "type": "TACTICAL",
            "title": "叙事事件错误携带数学修正",
            "severity": "MINOR",
            "impact": {"attack_lambda_delta": 0.1},
            "impact_mode": "NARRATIVE",
        })
        assert narrative_with_lambda.status_code == 400
        assert "不能包含非零" in narrative_with_lambda.json()["detail"]

    async def test_event_csv_import_is_validated_and_deduplicated(self, client):
        template = await client.get("/api/v1/events/import/template")
        assert template.status_code == 200
        assert "fifa_code" in template.text

        csv_content = (
            "fifa_code,type,title,description,severity,impact,source,source_type,source_url,external_id,effective_at,expires_at,active\n"
            "ARG,MORALE,批量导入事件,测试说明,MAJOR,\"{\"\"team_morale\"\":0.1}\",测试来源,IMPORT,https://example.com,import-001,2026-01-01T00:00:00,2030-01-01T00:00:00,true\n"
            "XXX,INJURY,无效球队,测试,MINOR,{},测试来源,IMPORT,,invalid-001,,,true\n"
        )
        imported = await client.post(
            "/api/v1/events/import",
            files={"file": ("events.csv", csv_content.encode("utf-8"), "text/csv")},
        )
        assert imported.status_code == 200
        result = imported.json()
        assert result["created"] == 1
        assert result["failed"] == 1
        assert result["errors"][0]["row"] == 3

        duplicate = await client.post(
            "/api/v1/events/import",
            files={"file": ("events.csv", csv_content.splitlines()[0].encode("utf-8") + b"\n" + csv_content.splitlines()[1].encode("utf-8") + b"\n", "text/csv")},
        )
        assert duplicate.json()["skipped"] == 1

        update_payload = [{
            "fifa_code": "ARG", "type": "MORALE", "title": "批量导入事件",
            "description": "更新后的说明", "severity": "CRITICAL",
            "source": "测试来源", "source_type": "IMPORT", "external_id": "import-001",
        }]
        updated = await client.post(
            "/api/v1/events/import",
            files={"file": ("events.json", __import__("json").dumps(update_payload, ensure_ascii=False).encode("utf-8"), "application/json")},
        )
        assert updated.json()["updated"] == 1

    async def test_expired_events_are_kept_in_history_but_excluded_from_current_list(self, client):
        created = await client.post("/api/v1/events", json={
            "team_id": 1,
            "type": "OTHER",
            "title": "已经到期的事件",
            "severity": "MINOR",
            "effective_at": "2020-01-01T00:00:00",
            "expires_at": "2020-01-02T00:00:00",
        })
        assert created.status_code == 200
        event_id = created.json()["id"]

        history = await client.get("/api/v1/events")
        assert event_id in {event["id"] for event in history.json()}

        current = await client.get("/api/v1/events?active_only=true&current_only=true")
        assert event_id not in {event["id"] for event in current.json()}

    async def test_event_list_exposes_status_tournament_and_legacy_warning(self, client):
        events = (await client.get("/api/v1/events")).json()
        legacy = next(event for event in events if "attack" in (event["impact"] or {}))
        assert legacy["status"] == "ACTIVE"
        assert legacy["status_label"] == "生效中"
        assert legacy["tournament"]["code"] == "world-cup-2026"
        assert legacy["needs_impact_migration"] is True
        assert legacy["legacy_impact_fields"] == ["attack"]

    async def test_event_api_validates_standard_modifiers_and_time_window(self, client):
        teams = (await client.get("/api/v1/teams")).json()
        team_id = teams[0]["id"]
        created = await client.post("/api/v1/events", json={
            "team_id": team_id,
            "type": "TACTICAL",
            "title": "标准修正字段测试",
            "impact": {
                "attack_lambda_delta": -0.1,
                "concede_lambda_delta": 0.2,
            },
            "effective_at": "2026-06-01T00:00:00",
            "expires_at": "2026-07-31T23:59:59",
        })
        assert created.status_code == 200
        assert created.json()["impact"] == {
            "attack_lambda_delta": -0.1,
            "concede_lambda_delta": 0.2,
        }
        assert created.json()["needs_impact_migration"] is False

        updated = await client.put(
            f'/api/v1/events/{created.json()["id"]}',
            json={
                "team_id": teams[1]["id"],
                "type": "OTHER",
                "description": None,
                "effective_at": None,
                "expires_at": None,
                "impact": {"attack": -0.05, "defense": 0.1},
            },
        )
        assert updated.status_code == 200
        assert updated.json()["team_id"] == teams[1]["id"]
        assert updated.json()["type"] == "OTHER"
        assert updated.json()["effective_at"] is None
        assert updated.json()["impact"] == {
            "attack_lambda_delta": -0.05,
            "concede_lambda_delta": 0.1,
        }
        assert updated.json()["needs_impact_migration"] is False

        extreme = await client.post("/api/v1/events", json={
            "team_id": team_id,
            "type": "TACTICAL",
            "title": "极端修正",
            "impact": {"attack_lambda_delta": -0.51},
        })
        assert extreme.status_code == 400

        invalid_window = await client.post("/api/v1/events", json={
            "team_id": team_id,
            "type": "TACTICAL",
            "title": "错误时间范围",
            "effective_at": "2026-08-01T00:00:00",
            "expires_at": "2026-07-01T00:00:00",
        })
        assert invalid_window.status_code == 400
        assert invalid_window.json()["detail"] == "失效时间必须晚于生效时间"

    async def test_expired_event_is_ignored_by_scenario_simulation(self, client):
        teams = (await client.get("/api/v1/teams")).json()
        event = await client.post("/api/v1/events", json={
            "team_id": teams[0]["id"],
            "type": "INJURY",
            "title": "过期情景事件",
            "impact": {"attack_lambda_delta": -0.5},
            "expires_at": "2020-01-01T00:00:00",
        })
        simulation = await client.get(
            f'/api/v1/bracket/simulation?iterations=100&event_ids={event.json()["id"]}'
        )
        assert simulation.status_code == 200
        assert simulation.json()["scenario"]["ignored_events"] == [{
            "event_id": event.json()["id"],
            "reason": "expired",
        }]


class TestPredictionsEndpoint:
    async def test_predict_match_returns_result(self, client):
        """单场分析必须从缓存模拟中解析权威数学上下文。"""
        simulation = await client.get("/api/v1/bracket/simulation?iterations=100")
        simulation_body = simulation.json()
        match = simulation_body["representative_path"]["stages"]["R32"]["matches"][0]
        resp = await client.post(
            "/api/v1/predictions/match",
            json={
                "simulation_id": simulation_body["simulation_id"],
                "match_key": match["match_key"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["simulation_id"] == simulation_body["simulation_id"]
        assert body["match_key"] == match["match_key"]
        assert body["math"]["predicted_score"] == (
            f'{match["home_score"]}-{match["away_score"]}'
        )
        assert body["math"]["winner_team_id"] == match["winner_team_id"]
        assert body["math"]["home_lambda"] > 0
        assert body["math"]["away_lambda"] > 0
        probabilities = body["math"]["probabilities"]
        assert probabilities["home_win"] + probabilities["draw"] + probabilities["away_win"] == pytest.approx(1.0, abs=0.001)
        assert body["agent"]["status"] in {"available", "agent_unavailable"}

    async def test_simulation_does_not_call_agent_until_match_click(
        self,
        client,
        monkeypatch,
    ):
        from unittest.mock import AsyncMock

        from app.routers.predictions import _get_prediction_service
        from app.schema.prediction_schema import (
            AgentReportValidationResult,
            ReasoningStep,
            ValidatedAgentReport,
        )

        service = _get_prediction_service()
        analyze = AsyncMock(return_value=AgentReportValidationResult(
            is_valid=True,
            cleaned_data=ValidatedAgentReport(
                key_factors=["数学结果与双方基础实力差距一致"],
                risk_notes=["代表路径不是唯一可能结果"],
                reasoning_chain=[ReasoningStep(
                    step_number=1,
                    finding="读取后端数学上下文",
                    analysis="仅解释既有比分和胜者",
                )],
            ),
        ))
        monkeypatch.setattr(service.agent, "analyze_simulated_match", analyze)

        simulation = await client.get("/api/v1/bracket/simulation?iterations=100")
        assert analyze.await_count == 0
        body = simulation.json()
        match = body["representative_path"]["stages"]["R32"]["matches"][0]
        response = await client.post(
            "/api/v1/predictions/match",
            json={
                "simulation_id": body["simulation_id"],
                "match_key": match["match_key"],
            },
        )
        assert response.status_code == 200
        assert analyze.await_count == 1
        assert response.json()["agent"]["status"] == "available"
        agent_context = analyze.await_args.args[0]
        assert agent_context["simulation_id"] == body["simulation_id"]
        assert agent_context["match_key"] == match["match_key"]
        assert agent_context["predicted_score"] == f'{match["home_score"]}-{match["away_score"]}'
        assert agent_context["winner_team_id"] == match["winner_team_id"]

    async def test_predict_match_rejects_stale_context_and_unknown_match(self, client):
        stale = await client.post(
            "/api/v1/predictions/match",
            json={"simulation_id": "expired", "match_key": "R32-1"},
        )
        assert stale.status_code == 404

        simulation = await client.get("/api/v1/bracket/simulation?iterations=100")
        unknown_match = await client.post(
            "/api/v1/predictions/match",
            json={
                "simulation_id": simulation.json()["simulation_id"],
                "match_key": "FINAL-999",
            },
        )
        assert unknown_match.status_code == 404

    async def test_agent_breaker_keeps_math_context_available(self, client):
        from app.routers.predictions import _get_prediction_service

        service = _get_prediction_service()
        for _ in range(service.breaker._failure_threshold):
            service.breaker.record_failure()
        simulation = await client.get("/api/v1/bracket/simulation?iterations=100")
        body = simulation.json()
        match = body["representative_path"]["stages"]["FINAL"]["matches"][0]
        response = await client.post(
            "/api/v1/predictions/match",
            json={
                "simulation_id": body["simulation_id"],
                "match_key": match["match_key"],
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["math"]["predicted_score"] == f'{match["home_score"]}-{match["away_score"]}'
        assert result["agent"]["status"] == "agent_unavailable"

    async def test_match_analysis_uses_events_from_selected_scenario(self, client):
        baseline = await client.get("/api/v1/bracket/simulation?iterations=100")
        baseline_body = baseline.json()
        baseline_match = baseline_body["representative_path"]["stages"]["R32"]["matches"][0]
        team = baseline_match["home_team"]
        event = await client.post("/api/v1/events", json={
            "team_id": team["id"],
            "type": "TACTICAL",
            "title": "单场上下文事件",
            "severity": "MINOR",
            "impact": {"attack_lambda_delta": -0.000001},
        })
        scenario = await client.get(
            f'/api/v1/bracket/simulation?iterations=100&event_ids={event.json()["id"]}'
            f'&baseline_simulation_id={baseline_body["simulation_id"]}'
        )
        scenario_body = scenario.json()
        scenario_match = next(
            match
            for stage in scenario_body["representative_path"]["stages"].values()
            for match in stage["matches"]
            if team["id"] in {
                match["home_team"]["id"],
                match["away_team"]["id"],
            }
        )
        response = await client.post("/api/v1/predictions/match", json={
            "simulation_id": scenario_body["simulation_id"],
            "match_key": scenario_match["match_key"],
        })
        assert response.status_code == 200
        math_context = response.json()["math"]
        assert math_context["scenario_type"] == "EVENT"
        assert [item["title"] for item in math_context["math_events"]] == [
            "单场上下文事件"
        ]


class TestBracketEndpoint:
    async def test_legacy_database_bracket_endpoint_is_removed(self, client):
        resp = await client.get("/api/v1/bracket")
        assert resp.status_code == 404

    async def test_simulation_returns_complete_stable_bracket(self, client):
        first = await client.get("/api/v1/bracket/simulation?iterations=100")
        assert first.status_code == 200
        body = first.json()
        assert body["simulation_id"]
        assert body["baseline_simulation_id"] == body["simulation_id"]
        assert body["scenario"]["type"] == "BASELINE"
        assert body["tournament"]["data_version"] == "user-scenario-20260713-v1"
        assert body["model"]["seed"] > 0
        assert body["scenario"]["requested_event_ids"] == []
        stages = body["representative_path"]["stages"]
        group_stage = body["representative_path"]["group_stage"]
        assert set(group_stage) == set("ABCDEFGHIJKL")
        assert all(len(group["matches"]) == 6 for group in group_stage.values())
        assert all(len(group["standings"]) == 4 for group in group_stage.values())
        assert all(
            match["winner_team_id"] is None
            or match["winner_team_id"] in {
                match["home_team"]["id"], match["away_team"]["id"]
            }
            for group in group_stage.values()
            for match in group["matches"]
        )
        assert {stage: len(stages[stage]["matches"]) for stage in ("R32", "R16", "QF", "SF", "FINAL")} == {
            "R32": 16, "R16": 8, "QF": 4, "SF": 2, "FINAL": 1,
        }
        all_matches = [
            match
            for stage in stages.values()
            for match in stage["matches"]
        ]
        assert all(match["match_key"] for match in all_matches)
        assert all(match["home_team"]["id"] > 0 for match in all_matches)
        assert all(match["away_team"]["id"] > 0 for match in all_matches)
        assert all(match["winner_team_id"] > 0 for match in all_matches)
        assert body["representative_path"]["champion"]["id"] == body["summary"][
            "probability_leader"
        ]["team"]["id"]
        assert stages["FINAL"]["matches"][0]["winner_team_id"] == body["summary"][
            "probability_leader"
        ]["team"]["id"]
        assert all(len(match["source_slots"]) == 2 for match in all_matches)
        assert all(
            source.startswith("GROUP_")
            for match in stages["R32"]["matches"]
            for source in match["source_slots"]
        )
        assert set(stages["R16"]["matches"][0]["source_slots"]) == {
            "R32-1", "R32-2"
        }
        assert set(stages["FINAL"]["matches"][0]["source_slots"]) == {
            "SF-1", "SF-2"
        }
        assert stages["FINAL"]["matches"][0]["winner_team_id"] == body[
            "representative_path"
        ]["champion"]["id"]

        cached = await client.get("/api/v1/bracket/simulation?iterations=100")
        assert cached.json()["simulation_id"] == body["simulation_id"]

        refreshed = await client.get("/api/v1/bracket/simulation?iterations=100&refresh=true")
        assert refreshed.json()["simulation_id"] != body["simulation_id"]
        assert refreshed.json()["model"]["seed"] != body["model"]["seed"]

    async def test_simulation_returns_event_application_audit(self, client):
        teams = (await client.get("/api/v1/teams")).json()
        argentina = next(team for team in teams if team["fifa_code"] == "ARG")
        created = await client.post("/api/v1/events", json={
            "team_id": argentina["id"],
            "type": "INJURY",
            "title": "进攻核心缺阵",
            "severity": "MAJOR",
            "impact": {"attack": -0.1},
        })
        event_id = created.json()["id"]

        response = await client.get(
            f"/api/v1/bracket/simulation?iterations=100&event_ids={event_id},999999"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["scenario"]["type"] == "EVENT"
        assert body["baseline_simulation_id"] != body["simulation_id"]
        assert body["scenario"]["requested_event_ids"] == [event_id, 999999]
        assert body["scenario"]["team_impacts"]["ARG"] == {
            "attack_lambda_delta": -0.1,
            "concede_lambda_delta": 0.0,
        }
        assert [event["event_id"] for event in body["scenario"]["math_events"]] == [event_id]
        assert body["scenario"]["ignored_events"] == [
            {"event_id": 999999, "reason": "not_found"}
        ]

    async def test_narrative_only_scenario_reuses_baseline_and_reaches_match_ai_context(
        self,
        client,
        monkeypatch,
    ):
        baseline = await client.get(
            "/api/v1/bracket/simulation?iterations=100&seed=24680"
        )
        baseline_body = baseline.json()
        match = baseline_body["representative_path"]["stages"]["R32"]["matches"][0]
        team = match["home_team"]
        event = await client.post("/api/v1/events", json={
            "team_id": team["id"],
            "type": "MORALE",
            "title": "仅供 AI 解读的背景",
            "description": "不会改变客观胜率模型",
            "severity": "MINOR",
            "impact": {"team_morale": 0.1},
            "impact_mode": "NARRATIVE",
        })
        event_id = event.json()["id"]

        class FailingEngine:
            def run(self, *args, **kwargs):
                raise AssertionError("纯叙事情景不应重新运行蒙特卡洛模拟")

        from app.routers import bracket as bracket_router

        monkeypatch.setattr(bracket_router, "get_engine", lambda: FailingEngine())
        scenario = await client.get(
            f"/api/v1/bracket/simulation?iterations=100&event_ids={event_id}"
            f"&baseline_simulation_id={baseline_body['simulation_id']}"
        )
        assert scenario.status_code == 200
        body = scenario.json()
        assert body["summary"] == baseline_body["summary"]
        assert body["representative_path"] == baseline_body["representative_path"]
        assert body["model"] == baseline_body["model"]
        assert body["scenario"]["math_events"] == []
        assert [item["event_id"] for item in body["scenario"]["narrative_events"]] == [event_id]
        assert body["scenario"]["ignored_events"] == []
        assert "数学基线不变" in body["scenario"]["label"]

        analysis = await client.post("/api/v1/predictions/match", json={
            "simulation_id": body["simulation_id"],
            "match_key": match["match_key"],
        })
        assert analysis.status_code == 200
        math_context = analysis.json()["math"]
        assert math_context["math_events"] == []
        assert [
            item["title"] for item in math_context["narrative_events"]
        ] == ["仅供 AI 解读的背景"]

    async def test_simulation_seed_is_reproducible(self, client):
        first = await client.get(
            "/api/v1/bracket/simulation?iterations=100&seed=20260713&refresh=true"
        )
        second = await client.get(
            "/api/v1/bracket/simulation?iterations=100&seed=20260713&refresh=true"
        )

        assert first.status_code == second.status_code == 200
        first_body = first.json()
        second_body = second.json()
        assert first_body["model"]["seed"] == second_body["model"]["seed"] == 20260713
        assert first_body["model"]["input_fingerprint"] == second_body["model"]["input_fingerprint"]
        assert first_body["summary"] == second_body["summary"]
        assert first_body["representative_path"] == second_body["representative_path"]
        assert all(
            match["decided_by"] in {"REGULAR_TIME", "PENALTIES"}
            for stage in first_body["representative_path"]["stages"].values()
            for match in stage["matches"]
        )

    async def test_event_scenario_reuses_explicit_baseline(self, client):
        baseline = await client.get(
            "/api/v1/bracket/simulation?iterations=100&seed=12345"
        )
        baseline_body = baseline.json()
        teams = (await client.get("/api/v1/teams")).json()
        argentina = next(team for team in teams if team["fifa_code"] == "ARG")
        event = await client.post("/api/v1/events", json={
            "team_id": argentina["id"],
            "type": "INJURY",
            "title": "基线关联测试",
            "severity": "MINOR",
            "impact": {"attack_lambda_delta": -0.05},
        })
        event_id = event.json()["id"]

        scenario = await client.get(
            f"/api/v1/bracket/simulation?iterations=100&event_ids={event_id}"
            f"&baseline_simulation_id={baseline_body['simulation_id']}"
        )
        scenario_body = scenario.json()

        assert scenario.status_code == 200
        assert scenario_body["baseline_simulation_id"] == baseline_body["simulation_id"]
        assert scenario_body["model"]["seed"] == baseline_body["model"]["seed"]
        assert scenario_body["scenario"]["type"] == "EVENT"

    async def test_data_sources_expose_verifiable_snapshot_and_transparency_notice(self, client):
        response = await client.get("/api/v1/data-sources")
        assert response.status_code == 200
        body = response.json()
        scenario = next(source for source in body["sources"] if source["id"] == "scenario_participants")
        assert scenario["verification_status"] == "VERIFIED_LOCAL"
        assert scenario["record_count"] == 48
        assert len(scenario["snapshot_sha256"]) == 64
        assert scenario["snapshot_bytes"] > 0
        assert scenario["is_official"] is False
        assert "非官方" in body["transparency_notice"]
        assert any(source["is_official"] for source in body["sources"])
        assert any(source["verification_status"] == "PENDING_NETWORK_REFRESH" for source in body["sources"])

    async def test_tournament_report_uses_complete_simulation_context(self, client, monkeypatch):
        from app.routers import predictions as predictions_router
        from app.services.prediction_service import PredictionService

        simulation = await client.get("/api/v1/bracket/simulation?iterations=100&seed=20260714")
        simulation_body = simulation.json()
        captured = {}

        class FakeAgent:
            async def analyze_tournament(self, context):
                captured.update(context)
                return {
                    "champion_summary": "冠军沿既有代表路径完成夺冠。",
                    "group_stage_reasoning": ["小组赛积分和晋级名额来自数学模拟。"],
                    "knockout_reasoning": ["淘汰赛逐轮比分保持后端结果。"],
                    "final_reasoning": "决赛解释不修改既有比分。",
                    "key_factors": ["ELO 实力基线"],
                    "event_analysis": [],
                    "alternative_outcomes": ["代表路径不是唯一可能结果。"],
                    "risk_notes": ["概率榜来自有限次数蒙特卡洛模拟。"],
                    "reasoning_chain": [{"step_number": 1, "finding": "读取完整赛事路径"}],
                }

        service = PredictionService(agent_service=FakeAgent())
        monkeypatch.setattr(predictions_router, "_prediction_service", service)
        response = await client.post("/api/v1/predictions/tournament-report", json={
            "simulation_id": simulation_body["simulation_id"],
        })
        assert response.status_code == 200
        body = response.json()
        final = simulation_body["representative_path"]["stages"]["FINAL"]["matches"][0]
        assert body["math"]["champion"]["id"] == simulation_body["representative_path"]["champion"]["id"]
        assert body["math"]["final_score"] == f'{final["home_score"]}-{final["away_score"]}'
        assert len(body["math"]["group_qualifiers"]) == 32
        assert len(body["math"]["knockout_path"]) == 31
        assert captured["champion"] == body["math"]["champion"]
        assert body["agent"]["status"] == "available"

    async def test_tournament_report_rejects_expired_simulation(self, client):
        response = await client.post("/api/v1/predictions/tournament-report", json={"simulation_id": "expired"})
        assert response.status_code == 404

    async def test_event_scenario_rejects_unknown_baseline(self, client):
        response = await client.get(
            "/api/v1/bracket/simulation?iterations=100&event_ids=999999"
            "&baseline_simulation_id=missing-baseline"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "基线模拟不存在或已过期"
