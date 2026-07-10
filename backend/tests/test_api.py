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
    from app.routers.predictions import _prediction_service

    _prediction_service.breaker.reset()


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
        """GET /api/v1/teams 应返回 48 支球队。"""
        resp = await client.get("/api/v1/teams")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 48


class TestEventsEndpoint:
    async def test_events_returns_json_array(self, client):
        """GET /api/v1/events 应返回 JSON 数组。"""
        resp = await client.get("/api/v1/events")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


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


class TestBracketEndpoint:
    async def test_bracket_returns_structure(self, client):
        """GET /api/v1/bracket 应返回对阵树结构。"""
        resp = await client.get("/api/v1/bracket")
        assert resp.status_code == 200
        body = resp.json()
        assert "stages" in body
        assert "total_matches" in body
