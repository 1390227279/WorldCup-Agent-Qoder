"""Tournament and tournament participant models."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.database import Base


DEFAULT_TOURNAMENT_CODE = "world-cup-2026"
DEFAULT_TOURNAMENT_NAME = "FIFA World Cup 2026"
DEFAULT_TOURNAMENT_NAME_CN = "2026 世界杯"
DEFAULT_TOURNAMENT_STATUS = "DRAFT"
DEFAULT_TOURNAMENT_DATA_VERSION = "legacy-seed-v1"
DEFAULT_TOURNAMENT_RULES_VERSION = "pending-v1"


class Tournament(Base):
    """A versioned tournament edition."""

    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(150), nullable=False)
    name_cn = Column(String(150), nullable=False)
    year = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default=DEFAULT_TOURNAMENT_STATUS)
    data_version = Column(
        String(100), nullable=False, default=DEFAULT_TOURNAMENT_DATA_VERSION
    )
    rules_version = Column(
        String(100), nullable=False, default=DEFAULT_TOURNAMENT_RULES_VERSION
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    participants = relationship(
        "TournamentTeam",
        back_populates="tournament",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "name_cn": self.name_cn,
            "year": self.year,
            "status": self.status,
            "data_version": self.data_version,
            "rules_version": self.rules_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TournamentTeam(Base):
    """A team's participation and tournament-specific attributes."""

    __tablename__ = "tournament_teams"
    __table_args__ = (
        UniqueConstraint(
            "tournament_id", "team_id", name="uq_tournament_teams_tournament_team"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tournament_id = Column(
        Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False
    )
    team_id = Column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    group_name = Column(String(2), nullable=True)
    pot = Column(Integer, nullable=True)
    qualification_status = Column(String(20), nullable=False, default="PENDING")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    tournament = relationship(
        "Tournament", back_populates="participants", lazy="selectin"
    )
    team = relationship("Team", back_populates="tournament_entries", lazy="selectin")

    def to_dict(self):
        return {
            "id": self.id,
            "tournament_id": self.tournament_id,
            "team_id": self.team_id,
            "group_name": self.group_name,
            "pot": self.pot,
            "qualification_status": self.qualification_status,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
