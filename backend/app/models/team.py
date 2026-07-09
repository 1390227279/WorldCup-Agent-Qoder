"""Team model."""

from sqlalchemy import Column, Integer, String, Float, JSON
from sqlalchemy.orm import relationship

from app.models.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    name_cn = Column(String(100), nullable=False)
    fifa_code = Column(String(3), nullable=False, unique=True)
    confederation = Column(String(10), nullable=False)
    fifa_ranking = Column(Integer, nullable=True)
    elo_rating = Column(Float, nullable=True)
    group_name = Column(String(2), nullable=True)  # A-L
    pot = Column(Integer, nullable=True)  # 1-4
    stats = Column(JSON, nullable=True)  # {"world_cup_titles": 2, "best_result": "Champion", ...}

    # Relationships
    events = relationship("Event", back_populates="team", lazy="selectin")
    home_matches = relationship(
        "Match", foreign_keys="Match.home_team_id", back_populates="home_team", lazy="selectin"
    )
    away_matches = relationship(
        "Match", foreign_keys="Match.away_team_id", back_populates="away_team", lazy="selectin"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_cn": self.name_cn,
            "fifa_code": self.fifa_code,
            "confederation": self.confederation,
            "fifa_ranking": self.fifa_ranking,
            "elo_rating": self.elo_rating,
            "group_name": self.group_name,
            "pot": self.pot,
            "stats": self.stats,
        }
