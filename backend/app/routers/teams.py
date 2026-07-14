"""Team-related API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.team import Team
from app.models.tournament import DEFAULT_TOURNAMENT_CODE, Tournament, TournamentTeam

router = APIRouter()


@router.get("")
async def list_teams(db: AsyncSession = Depends(get_db)):
    """List the current tournament's 48 active participants."""
    result = await db.execute(
        select(Team, TournamentTeam, Tournament)
        .join(TournamentTeam, TournamentTeam.team_id == Team.id)
        .join(Tournament, Tournament.id == TournamentTeam.tournament_id)
        .where(
            Tournament.code == DEFAULT_TOURNAMENT_CODE,
            TournamentTeam.active.is_(True),
        )
        .order_by(TournamentTeam.group_name, TournamentTeam.pot)
    )
    response = []
    for team, participant, tournament in result.all():
        data = team.to_dict()
        data["tournament"] = {
            "id": tournament.id,
            "code": tournament.code,
            "name": tournament.name,
            "name_cn": tournament.name_cn,
            "year": tournament.year,
            "status": tournament.status,
            "data_version": tournament.data_version,
            "group_name": participant.group_name,
            "pot": participant.pot,
            "qualification_status": participant.qualification_status,
        }
        response.append(data)
    return response


@router.get("/{team_id}")
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single team with its active events."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalars().first()
    if not team:
        raise HTTPException(status_code=404, detail="球队不存在")
    data = team.to_dict()
    participant_result = await db.execute(
        select(TournamentTeam, Tournament)
        .join(Tournament, Tournament.id == TournamentTeam.tournament_id)
        .where(
            Tournament.code == DEFAULT_TOURNAMENT_CODE,
            TournamentTeam.team_id == team.id,
            TournamentTeam.active.is_(True),
        )
    )
    participant_row = participant_result.first()
    if participant_row:
        participant, tournament = participant_row
        data["tournament"] = {
            "id": tournament.id,
            "code": tournament.code,
            "name": tournament.name,
            "name_cn": tournament.name_cn,
            "year": tournament.year,
            "status": tournament.status,
            "data_version": tournament.data_version,
            "group_name": participant.group_name,
            "pot": participant.pot,
            "qualification_status": participant.qualification_status,
        }
    data["events"] = [e.to_dict() for e in team.events if e.active]
    return data
