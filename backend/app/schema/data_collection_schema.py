from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CollectionRunStatus = Literal["FETCHING", "FETCHED", "PROCESSING", "COMPLETED", "FAILED"]


class DataCollectionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    source_name: str
    source_url: str | None
    started_at: datetime
    completed_at: datetime | None
    status: CollectionRunStatus
    http_status: int | None
    snapshot_path: str | None
    snapshot_bytes: int | None = Field(default=None, ge=0)
    sha256_hash: str | None = Field(default=None, min_length=64, max_length=64)
    raw_record_count: int = Field(ge=0)
    inserted_record_count: int = Field(ge=0)
    duplicate_record_count: int = Field(ge=0)
    updated_team_count: int = Field(ge=0)
    skipped_team_count: int = Field(ge=0)
    error_message: str | None


class DataCollectionSourceResponse(BaseModel):
    id: str
    name: str
    url: str


class DataCollectionProcessResponse(BaseModel):
    run_id: int
    status: CollectionRunStatus
    raw_record_count: int = Field(ge=0)
    updated_team_count: int = Field(ge=0)
    skipped_team_count: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)
    message: str
