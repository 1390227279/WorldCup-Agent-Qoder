"""Match model."""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.models.database import Base


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stage = Column(String(20), nullable=False)  # GROUP, R32, R16, QF, SF, THIRD, FINAL
    round_name = Column(String(50), nullable=True)  # "Group A - Round 1", "Round of 32"
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    is_simulated = Column(Boolean, default=True)
    match_order = Column(Integer, nullable=True)  # sorting order in bracket

    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")

    def to_dict(self):
        return {
            "id": self.id,
            "stage": self.stage,
            "round_name": self.round_name,
            "home_team": self.home_team.to_dict() if self.home_team else None,
            "away_team": self.away_team.to_dict() if self.away_team else None,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "is_simulated": self.is_simulated,
        }
