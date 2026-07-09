"""Team-related API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.team import Team

router = APIRouter()


@router.get("")
async def list_teams(db: AsyncSession = Depends(get_db)):
    """List all 48 teams with their group assignments."""
    result = await db.execute(select(Team).order_by(Team.group_name, Team.pot))
    teams = result.scalars().all()
    return [t.to_dict() for t in teams]


@router.get("/{team_id}")
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single team with its active events."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalars().first()
    if not team:
        return {"error": "Team not found"}, 404
    data = team.to_dict()
    data["events"] = [e.to_dict() for e in team.events if e.active]
    return data
