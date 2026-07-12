"""Event API routes — manage dynamic team events."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import get_db
from app.models.event import Event
from app.models.team import Team

logger = logging.getLogger(__name__)

router = APIRouter()

class EventCreate(BaseModel):
    team_id: int
    type: str
    title: str
    description: Optional[str] = None
    severity: str = "MINOR"
    impact: Optional[dict] = None
    source: Optional[str] = None

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    impact: Optional[dict] = None
    active: Optional[bool] = None

TYPE_LABELS = {"INJURY": "伤病", "COACHING": "教练变动", "TACTICAL": "战术调整", "MORALE": "士气", "OTHER": "其他"}
SEVERITY_LABELS = {"CRITICAL": "严重", "MAJOR": "重要", "MINOR": "一般"}

def _event_to_dict(event: Event) -> dict:
    d = event.to_dict()
    if event.team:
        d["team_name"] = event.team.name_cn
        d["fifa_code"] = event.team.fifa_code
    d["type_label"] = TYPE_LABELS.get(event.type, event.type)
    d["severity_label"] = SEVERITY_LABELS.get(event.severity, event.severity)
    return d

@router.get("/types")
async def get_event_types():
    return {"types": TYPE_LABELS, "severities": SEVERITY_LABELS}

@router.get("")
async def list_events(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Event).options(selectinload(Event.team)).order_by(Event.created_at.desc())
    )
    events = result.scalars().all()
    return [_event_to_dict(e) for e in events]

@router.post("")
async def create_event(req: EventCreate, db: AsyncSession = Depends(get_db)):
    team = await db.get(Team, req.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="球队不存在")
    event = Event(
        team_id=req.team_id, type=req.type, title=req.title,
        description=req.description, severity=req.severity,
        impact=req.impact, source=req.source, active=True,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    result = await db.execute(
        select(Event).options(selectinload(Event.team)).where(Event.id == event.id)
    )
    event = result.scalar_one()
    return _event_to_dict(event)

@router.put("/{event_id}")
async def update_event(event_id: int, req: EventUpdate, db: AsyncSession = Depends(get_db)):
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    if req.title is not None:
        event.title = req.title
    if req.description is not None:
        event.description = req.description
    if req.severity is not None:
        if req.severity not in ("CRITICAL", "MAJOR", "MINOR"):
            raise HTTPException(status_code=400, detail="严重程度无效")
        event.severity = req.severity
    if req.impact is not None:
        event.impact = req.impact
    if req.active is not None:
        event.active = req.active
    await db.commit()
    result = await db.execute(
        select(Event).options(selectinload(Event.team)).where(Event.id == event_id)
    )
    event = result.scalar_one()
    return _event_to_dict(event)

@router.delete("/{event_id}")
async def delete_event(event_id: int, db: AsyncSession = Depends(get_db)):
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    await db.delete(event)
    await db.commit()
    return {"deleted": True}
