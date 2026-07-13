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

    _get_prediction_service().breaker.reset()


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
        assert {team["tournament_status"] for team in data} == {"SCENARIO"}
        assert {team["qualification_status"] for team in data} == {"SCENARIO"}


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
        event_id = created.json()["id"]

        after_create = await client.get("/api/v1/bracket/simulation?iterations=100")
        assert after_create.json()["simulation_id"] != initial_id

        updated = await client.put(f"/api/v1/events/{event_id}", json={"active": False})
        assert updated.status_code == 200
        assert updated.json()["active"] is False

        deleted = await client.delete(f"/api/v1/events/{event_id}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True

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


class TestPredictionsEndpoint:
    async def test_predict_match_returns_result(self, client):
        """POST /api/v1/predictions/match 应返回完整预测结果。"""
        resp = await client.post(
            "/api/v1/predictions/match",
            json={"home_team_id": 1, "away_team_id": 2},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "home_team" in body
        assert "away_team" in body
        assert "is_valid" in body
        assert "prediction" in body
        assert "circuit_breaker" in body
        assert body["prediction"]["predicted_score"]
        assert all(
            step["step_number"] > 0
            for step in body["prediction"]["reasoning_chain"]
        )

    async def test_predict_match_falls_back_to_fifa_code(self, client):
        """Stale bracket IDs can be recovered using stable FIFA codes."""
        resp = await client.post(
            "/api/v1/predictions/match",
            json={
                "home_team_id": 99991,
                "away_team_id": 99992,
                "home_team_code": "USA",
                "away_team_code": "NED",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["home_team"] == "United States"
        assert body["away_team"] == "Netherlands"


class TestBracketEndpoint:
    async def test_bracket_returns_structure(self, client):
        """GET /api/v1/bracket 应返回对阵树结构。"""
        resp = await client.get("/api/v1/bracket")
        assert resp.status_code == 200
        body = resp.json()
        assert "stages" in body
        assert "total_matches" in body

    async def test_simulation_returns_complete_stable_bracket(self, client):
        first = await client.get("/api/v1/bracket/simulation?iterations=100")
        assert first.status_code == 200
        body = first.json()
        assert body["simulation_id"]
        assert body["seed"] > 0
        assert body["event_ids"] == []
        assert {stage: len(body["stages"][stage]["matches"]) for stage in ("R32", "R16", "QF", "SF", "FINAL")} == {
            "R32": 16, "R16": 8, "QF": 4, "SF": 2, "FINAL": 1,
        }
        all_matches = [
            match
            for stage in body["stages"].values()
            for match in stage["matches"]
        ]
        assert all(match["match_key"] for match in all_matches)
        assert all(match["home_team"]["id"] > 0 for match in all_matches)
        assert all(match["away_team"]["id"] > 0 for match in all_matches)
        assert all(match["winner_team_id"] > 0 for match in all_matches)
        assert all(len(match["source_slots"]) == 2 for match in all_matches)
        assert all(
            source.startswith("GROUP_")
            for match in body["stages"]["R32"]["matches"]
            for source in match["source_slots"]
        )
        assert set(body["stages"]["R16"]["matches"][0]["source_slots"]) == {
            "R32-1", "R32-2"
        }
        assert set(body["stages"]["FINAL"]["matches"][0]["source_slots"]) == {
            "SF-1", "SF-2"
        }
        assert body["stages"]["FINAL"]["matches"][0]["winner"] == body["predicted_champion"]

        cached = await client.get("/api/v1/bracket/simulation?iterations=100")
        assert cached.json()["simulation_id"] == body["simulation_id"]

        refreshed = await client.get("/api/v1/bracket/simulation?iterations=100&refresh=true")
        assert refreshed.json()["simulation_id"] != body["simulation_id"]
