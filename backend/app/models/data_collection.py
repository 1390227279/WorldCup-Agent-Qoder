"""Persistent lineage ledger for external data collection runs."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class DataCollectionRun(Base):
    __tablename__ = "data_collection_runs"
    __table_args__ = (
        Index("ix_data_collection_runs_source_started", "source_name", "started_at"),
        Index("ix_data_collection_runs_status", "status"),
        Index("ix_data_collection_runs_sha256", "sha256_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="FETCHING")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    snapshot_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_team_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_team_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "http_status": self.http_status,
            "snapshot_path": self.snapshot_path,
            "snapshot_bytes": self.snapshot_bytes,
            "sha256_hash": self.sha256_hash,
            "raw_record_count": self.raw_record_count,
            "updated_team_count": self.updated_team_count,
            "skipped_team_count": self.skipped_team_count,
            "error_message": self.error_message,
        }
