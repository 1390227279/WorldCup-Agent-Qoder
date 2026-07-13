"""
Event Injector — provides dynamic event data to the Qwen Agent.

This is the service that lets Qwen ask "any injuries for team X?"
and get structured event data back.

The Agent's get_team_events tool internally calls this service.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.scenario_resolver import event_is_current


@dataclass
class EventSummary:
    """Lightweight event summary for Agent tool responses."""
    id: int
    team_name: str
    team_code: str
    type: str
    title: str
    description: str
    severity: str
    impact: dict
    source: str
    active: bool


@dataclass
class TeamEventReport:
    """Complete event report for one team."""
    team_name: str
    team_code: str
    active_events: list[EventSummary] = field(default_factory=list)
    total_impact: dict = field(default_factory=dict)  # aggregated impact across all events

    @property
    def has_critical(self) -> bool:
        return any(e.severity == "CRITICAL" for e in self.active_events)

    @property
    def has_major(self) -> bool:
        return any(e.severity in ("CRITICAL", "MAJOR") for e in self.active_events)

    @property
    def event_count(self) -> int:
        return len(self.active_events)


class EventInjector:
    """
    Provides event data for Agent tool consumption.

    The Agent calls get_team_events("France"), and this service
    queries the database for any active events on that team,
    returning a structured report the Agent can reason about.

    Usage:
        injector = EventInjector(db_session)
        report = await injector.get_team_events("France")
        # report.active_events → list of injuries, coaching changes, etc.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_team_events(self, team_code: str) -> Optional[TeamEventReport]:
        """
        Get all active events for a team.

        This is the function called by the Agent's get_team_events tool.
        Returns None if the team doesn't exist in our database.
        """
        # Get team
        from app.models.team import Team
        result = await self.db.execute(
            select(Team).where(Team.fifa_code == team_code.upper())
        )
        team = result.scalars().first()
        if not team:
            return None

        # Get active events
        report = TeamEventReport(team_name=team.name, team_code=team.fifa_code)
        for event in team.events:
            if not event_is_current(event):
                continue
            summary = EventSummary(
                id=event.id,
                team_name=team.name,
                team_code=team.fifa_code,
                type=event.type,
                title=event.title,
                description=event.description or "",
                severity=event.severity,
                impact=event.impact or {},
                source=event.source or "Unknown",
                active=event.active,
            )
            report.active_events.append(summary)

        # Aggregate total impact
        total = {}
        for e in report.active_events:
            for key, value in e.impact.items():
                total[key] = total.get(key, 0) + value
        report.total_impact = total

        return report

    async def get_all_active_events(self) -> list[EventSummary]:
        """Get all active events across all teams."""
        from app.models.event import Event
        result = await self.db.execute(select(Event).where(Event.active == True))
        events = result.scalars().all()

        summaries: list[EventSummary] = []
        for e in events:
            if not event_is_current(e):
                continue
            summaries.append(EventSummary(
                id=e.id,
                team_name=e.team.name if e.team else "Unknown",
                team_code=e.team.fifa_code if e.team else "???",
                type=e.type,
                title=e.title,
                description=e.description or "",
                severity=e.severity,
                impact=e.impact or {},
                source=e.source or "Unknown",
                active=e.active,
            ))
        return summaries

    def format_for_agent(self, report: TeamEventReport) -> str:
        """
        Format an event report as human-readable text for the Agent's context window.

        The Agent sees this text when it calls get_team_events.
        """
        if not report.active_events:
            return f"{report.team_name} ({report.team_code}): 当前无活跃事件。"

        lines = [f"### {report.team_name} ({report.team_code}) 活跃事件:"]
        for e in report.active_events:
            severity_icon = {"CRITICAL": "🔴", "MAJOR": "🟡", "MINOR": "🔵"}.get(
                e.severity, "⚪"
            )
            lines.append(
                f"- {severity_icon} [{e.severity}] {e.title}\n"
                f"  类型: {e.type} | 描述: {e.description}\n"
                f"  量化影响: {json.dumps(e.impact, ensure_ascii=False)}\n"
                f"  来源: {e.source}"
            )

        if report.total_impact:
            lines.append(f"\n总计影响: {json.dumps(report.total_impact, ensure_ascii=False)}")

        return "\n".join(lines)
