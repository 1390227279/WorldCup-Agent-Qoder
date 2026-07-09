"""AgentPrediction model — stores both Agent decisions and fallback statistical predictions."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.models.database import Base


class AgentPrediction(Base):
    __tablename__ = "agent_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, unique=True)
    winner = Column(String(100), nullable=True)  # team name or "draw"
    predicted_score = Column(String(50), nullable=True)  # "2-1" or "1-1 (4-2 pens)"
    confidence = Column(Float, nullable=True)  # 0-1
    key_factors = Column(JSON, nullable=True)  # ["factor1", "factor2", ...]
    reasoning_chain = Column(JSON, nullable=True)  # [{"step": 1, "tool": "...", "finding": "..."}, ...]
    is_agent = Column(Boolean, default=True)  # True=Qwen decision, False=statistical fallback
    model_used = Column(String(50), nullable=True)  # "qwen-max" / "poisson-statistical"
    tool_calls_log = Column(JSON, nullable=True)  # record of tool calls Qwen made
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    match = relationship("Match")

    def to_dict(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "winner": self.winner,
            "predicted_score": self.predicted_score,
            "confidence": self.confidence,
            "key_factors": self.key_factors,
            "reasoning_chain": self.reasoning_chain,
            "is_agent": self.is_agent,
            "model_used": self.model_used,
            "tool_calls_log": self.tool_calls_log,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
