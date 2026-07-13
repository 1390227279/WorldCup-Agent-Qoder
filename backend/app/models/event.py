"""Event model for dynamic factors (injuries, coaching changes, etc.)."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.models.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    type = Column(String(20), nullable=False)  # INJURY, COACHING, TACTICAL, MORALE, OTHER
    title = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    severity = Column(String(10), nullable=False, default="MINOR")  # CRITICAL, MAJOR, MINOR
    # Canonical simulator keys: attack_lambda_delta, concede_lambda_delta.
    # Other keys remain available to the Agent as qualitative context.
    impact = Column(JSON, nullable=True)
    source = Column(String(200), nullable=True)
    source_type = Column(String(30), nullable=False, default="MANUAL")
    source_url = Column(String(500), nullable=True)
    external_id = Column(String(200), nullable=True, index=True)
    effective_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    team = relationship("Team", back_populates="events")

    def to_dict(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "impact": self.impact,
            "source": self.source,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "external_id": self.external_id,
            "effective_at": self.effective_at.isoformat() if self.effective_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
