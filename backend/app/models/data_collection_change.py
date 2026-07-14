from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.database import Base

class DataCollectionChange(Base):
    __tablename__ = "data_collection_changes"
    __table_args__ = (Index("ix_data_collection_changes_run", "run_id"), Index("ix_data_collection_changes_team", "team_id"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("data_collection_runs.id"), nullable=False)
    record_type: Mapped[str] = mapped_column(String(50), nullable=False)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    fifa_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
