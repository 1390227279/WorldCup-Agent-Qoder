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
    impact = Column(JSON, nullable=True)  # {"attack": -0.20, "defense": 0, "cohesion": -0.10}
    source = Column(String(200), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

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
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
