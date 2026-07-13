"""Event API routes — manage dynamic team events."""

import logging
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import get_db
from app.models.event import Event
from app.models.team import Team
from app.models.tournament import (
    DEFAULT_TOURNAMENT_CODE,
    TournamentTeam,
)
from app.services.event_sources import FileEventSource
from app.services.scenario_resolver import (
    ATTACK_LAMBDA_DELTA,
    CONCEDE_LAMBDA_DELTA,
    MAX_EVENT_DELTA,
    MIN_EVENT_DELTA,
    EventImpactError,
    normalize_impact_for_storage,
)
from app.services.simulation_cache import get_simulation_cache

logger = logging.getLogger(__name__)

router = APIRouter()

class EventCreate(BaseModel):
    team_id: int
    type: str
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    severity: str = "MINOR"
    impact: Optional[dict] = None
    source: Optional[str] = None
    source_type: str = "MANUAL"
    source_url: Optional[str] = None
    external_id: Optional[str] = None
    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class EventUpdate(BaseModel):
    team_id: Optional[int] = None
    type: Optional[str] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    severity: Optional[str] = None
    impact: Optional[dict] = None
    active: Optional[bool] = None
    source: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    external_id: Optional[str] = None
    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

TYPE_LABELS = {"INJURY": "伤病", "COACHING": "教练变动", "TACTICAL": "战术调整", "MORALE": "士气", "OTHER": "其他"}
SEVERITY_LABELS = {"CRITICAL": "严重", "MAJOR": "重要", "MINOR": "一般"}
STATUS_LABELS = {
    "ACTIVE": "生效中",
    "SCHEDULED": "待生效",
    "EXPIRED": "已过期",
    "INACTIVE": "已停用",
}


def _event_status(event: Event, now: datetime | None = None) -> str:
    current_time = now or datetime.utcnow()
    if not event.active:
        return "INACTIVE"
    if event.effective_at and event.effective_at > current_time:
        return "SCHEDULED"
    if event.expires_at and event.expires_at <= current_time:
        return "EXPIRED"
    return "ACTIVE"


def _event_load_options():
    return selectinload(Event.team).selectinload(
        Team.tournament_entries
    ).selectinload(TournamentTeam.tournament)


def _validate_event_window(
    effective_at: datetime | None,
    expires_at: datetime | None,
) -> None:
    if effective_at and expires_at and expires_at <= effective_at:
        raise ValueError("失效时间必须晚于生效时间")

def _event_to_dict(event: Event) -> dict:
    d = event.to_dict()
    if event.team:
        d["team_name"] = event.team.name_cn
        d["fifa_code"] = event.team.fifa_code
    d["type_label"] = TYPE_LABELS.get(event.type, event.type)
    d["severity_label"] = SEVERITY_LABELS.get(event.severity, event.severity)
    status = _event_status(event)
    d["status"] = status
    d["status_label"] = STATUS_LABELS[status]
    legacy_fields = [
        key for key in ("attack", "defense")
        if key in (event.impact or {})
    ]
    d["legacy_impact_fields"] = legacy_fields
    d["needs_impact_migration"] = bool(legacy_fields)
    if event.team:
        entries = [entry for entry in event.team.tournament_entries if entry.active]
        entry = next(
            (
                item for item in entries
                if item.tournament.code == DEFAULT_TOURNAMENT_CODE
            ),
            entries[0] if entries else None,
        )
        d["tournament"] = (
            {
                "id": entry.tournament.id,
                "code": entry.tournament.code,
                "name": entry.tournament.name,
                "name_cn": entry.tournament.name_cn,
                "year": entry.tournament.year,
            }
            if entry else None
        )
    return d

@router.get("/types")
async def get_event_types():
    return {
        "types": TYPE_LABELS,
        "severities": SEVERITY_LABELS,
        "impact_fields": {
            ATTACK_LAMBDA_DELTA: "本队进球期望修正",
            CONCEDE_LAMBDA_DELTA: "对手面对本队时的进球期望修正",
        },
        "impact_range": {"min": MIN_EVENT_DELTA, "max": MAX_EVENT_DELTA},
    }

@router.get("")
async def list_events(
    active_only: bool = Query(False),
    current_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Event).options(_event_load_options())
    now = datetime.utcnow()
    if active_only:
        stmt = stmt.where(Event.active == True)
    if current_only:
        stmt = stmt.where(
            or_(Event.effective_at.is_(None), Event.effective_at <= now),
            or_(Event.expires_at.is_(None), Event.expires_at > now),
        )
    result = await db.execute(stmt.order_by(Event.created_at.desc()))
    events = result.scalars().all()
    return [_event_to_dict(e) for e in events]

@router.post("")
async def create_event(req: EventCreate, db: AsyncSession = Depends(get_db)):
    team = await db.get(Team, req.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="球队不存在")
    if req.type not in TYPE_LABELS:
        raise HTTPException(status_code=400, detail="事件类型无效")
    if req.severity not in SEVERITY_LABELS:
        raise HTTPException(status_code=400, detail="严重程度无效")
    try:
        _validate_event_window(req.effective_at, req.expires_at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        normalized_impact = normalize_impact_for_storage(req.impact)
    except EventImpactError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    event = Event(
        team_id=req.team_id, type=req.type, title=req.title,
        description=req.description, severity=req.severity,
        impact=normalized_impact, source=req.source, active=True,
        source_type=req.source_type, source_url=req.source_url,
        external_id=req.external_id, effective_at=req.effective_at,
        expires_at=req.expires_at,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    get_simulation_cache().invalidate_scenarios({event.id})
    result = await db.execute(
        select(Event)
        .options(_event_load_options())
        .where(Event.id == event.id)
        .execution_options(populate_existing=True)
    )
    event = result.scalar_one()
    return _event_to_dict(event)

@router.put("/{event_id}")
async def update_event(event_id: int, req: EventUpdate, db: AsyncSession = Depends(get_db)):
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    fields_set = req.model_fields_set
    if req.team_id is not None:
        if not await db.get(Team, req.team_id):
            raise HTTPException(status_code=404, detail="球队不存在")
        event.team_id = req.team_id
    if req.type is not None:
        if req.type not in TYPE_LABELS:
            raise HTTPException(status_code=400, detail="事件类型无效")
        event.type = req.type
    if req.title is not None:
        event.title = req.title
    if "description" in fields_set:
        event.description = req.description
    if req.severity is not None:
        if req.severity not in ("CRITICAL", "MAJOR", "MINOR"):
            raise HTTPException(status_code=400, detail="严重程度无效")
        event.severity = req.severity
    if "impact" in fields_set:
        try:
            event.impact = normalize_impact_for_storage(req.impact)
        except EventImpactError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if req.active is not None:
        event.active = req.active
    effective_at = req.effective_at if "effective_at" in fields_set else event.effective_at
    expires_at = req.expires_at if "expires_at" in fields_set else event.expires_at
    try:
        _validate_event_window(effective_at, expires_at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    for field_name in (
        "source",
        "source_url",
        "external_id",
        "effective_at",
        "expires_at",
    ):
        if field_name in fields_set:
            setattr(event, field_name, getattr(req, field_name))
    if "source_type" in fields_set:
        if not req.source_type:
            raise HTTPException(status_code=400, detail="来源类型不能为空")
        event.source_type = req.source_type
    await db.commit()
    get_simulation_cache().invalidate_scenarios({event_id})
    result = await db.execute(
        select(Event)
        .options(_event_load_options())
        .where(Event.id == event_id)
        .execution_options(populate_existing=True)
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
    get_simulation_cache().invalidate_scenarios({event_id})
    return {"deleted": True}


def _parse_datetime(value) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def _parse_impact(value) -> Optional[dict]:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        return value
    parsed = json.loads(str(value))
    if not isinstance(parsed, dict):
        raise ValueError("impact 必须是 JSON 对象")
    return parsed


@router.get("/import/template")
async def download_import_template():
    content = (
        "fifa_code,type,title,description,severity,impact,source,source_type,source_url,external_id,effective_at,expires_at,active\n"
        "ARG,INJURY,示例事件,事件说明,MAJOR,\"{\"\"attack_lambda_delta\"\":-0.1}\",官方公告,IMPORT,https://example.com,event-001,2026-06-01T00:00:00,2026-07-31T23:59:59,true\n"
    )
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=event-import-template.csv"},
    )


@router.post("/import")
async def import_events(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        records = FileEventSource().parse(file.filename or "", await file.read())
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    teams = (await db.execute(select(Team))).scalars().all()
    team_by_code = {team.fifa_code.upper(): team for team in teams}
    existing_events = (await db.execute(select(Event))).scalars().all()
    by_external = {
        (event.source_type or "MANUAL", event.external_id): event
        for event in existing_events if event.external_id
    }
    by_fingerprint = {
        (event.team_id, event.type, event.title.strip(), event.source or ""): event
        for event in existing_events
    }

    created = updated = skipped = 0
    errors: list[dict] = []
    for row_number, raw in enumerate(records, start=2):
        try:
            code = str(raw.get("fifa_code", "")).strip().upper()
            team = team_by_code.get(code)
            if not team:
                raise ValueError(f"未知 FIFA code：{code or '空'}")
            event_type = str(raw.get("type", "")).strip().upper()
            severity = str(raw.get("severity", "MINOR")).strip().upper()
            title = str(raw.get("title", "")).strip()
            if event_type not in TYPE_LABELS:
                raise ValueError(f"事件类型无效：{event_type}")
            if severity not in SEVERITY_LABELS:
                raise ValueError(f"严重程度无效：{severity}")
            if not title:
                raise ValueError("标题不能为空")
            source_type = str(raw.get("source_type", "IMPORT") or "IMPORT").strip().upper()
            external_id = str(raw.get("external_id", "") or "").strip() or None
            source = str(raw.get("source", "") or "").strip() or None
            active_raw = str(raw.get("active", "true")).strip().lower()
            payload = {
                "team_id": team.id,
                "type": event_type,
                "title": title,
                "description": str(raw.get("description", "") or "").strip() or None,
                "severity": severity,
                "impact": normalize_impact_for_storage(_parse_impact(raw.get("impact"))),
                "source": source,
                "source_type": source_type,
                "source_url": str(raw.get("source_url", "") or "").strip() or None,
                "external_id": external_id,
                "effective_at": _parse_datetime(raw.get("effective_at")),
                "expires_at": _parse_datetime(raw.get("expires_at")),
                "active": active_raw not in ("false", "0", "no", "否"),
            }
            _validate_event_window(payload["effective_at"], payload["expires_at"])
            event = by_external.get((source_type, external_id)) if external_id else None
            event = event or by_fingerprint.get((team.id, event_type, title, source or ""))
            if event:
                changed = any(getattr(event, key) != value for key, value in payload.items())
                if changed:
                    for key, value in payload.items():
                        setattr(event, key, value)
                    updated += 1
                else:
                    skipped += 1
            else:
                event = Event(**payload)
                db.add(event)
                created += 1
                if external_id:
                    by_external[(source_type, external_id)] = event
                by_fingerprint[(team.id, event_type, title, source or "")] = event
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append({"row": row_number, "error": str(exc)})

    await db.commit()
    if created or updated:
        get_simulation_cache().invalidate_scenarios()
    return {
        "filename": file.filename,
        "total": len(records),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "failed": len(errors),
        "errors": errors,
    }
