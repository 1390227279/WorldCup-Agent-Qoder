"""Normalized historical matches imported from traceable external snapshots."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class HistoricalMatch(Base):
    __tablename__ = "historical_matches"
    __table_args__ = (
        UniqueConstraint("match_fingerprint", name="uq_historical_matches_fingerprint"),
        Index("ix_historical_matches_date", "match_date"),
        Index("ix_historical_matches_home_team", "home_team_id"),
        Index("ix_historical_matches_away_team", "away_team_id"),
        Index("ix_historical_matches_source_run", "source_run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_date: Mapped[date] = mapped_column(Date, nullable=False)
    tournament: Mapped[str] = mapped_column(String(200), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    home_fifa_code: Mapped[str] = mapped_column(String(3), nullable=False)
    away_fifa_code: Mapped[str] = mapped_column(String(3), nullable=False)
    home_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    away_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_run_id: Mapped[int] = mapped_column(ForeignKey("data_collection_runs.id"), nullable=False)
    external_match_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    match_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
