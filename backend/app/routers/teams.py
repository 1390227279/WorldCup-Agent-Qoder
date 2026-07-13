"""Team-related API routes."""

from fastapi import APIRouter, Depends
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
        data["group_name"] = participant.group_name
        data["pot"] = participant.pot
        data["qualification_status"] = participant.qualification_status
        data["tournament_status"] = tournament.status
        data["tournament_data_version"] = tournament.data_version
        response.append(data)
    return response


@router.get("/{team_id}")
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single team with its active events."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalars().first()
    if not team:
        return {"error": "Team not found"}, 404
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
        data["group_name"] = participant.group_name
        data["pot"] = participant.pot
        data["qualification_status"] = participant.qualification_status
        data["tournament_status"] = tournament.status
        data["tournament_data_version"] = tournament.data_version
    data["events"] = [e.to_dict() for e in team.events if e.active]
    return data
