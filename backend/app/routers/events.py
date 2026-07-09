"""Event API routes — manage dynamic team events."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.event import Event

router = APIRouter()


@router.get("")
async def list_events(db: AsyncSession = Depends(get_db)):
    """List all active events."""
    result = await db.execute(
        select(Event).where(Event.active == True)
    )
    events = result.scalars().all()
    return [e.to_dict() for e in events]


@router.post("")
async def create_event(event_data: dict, db: AsyncSession = Depends(get_db)):
    """Add a new dynamic event (injury, coaching change, etc.)."""
    event = Event(**event_data)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event.to_dict()
