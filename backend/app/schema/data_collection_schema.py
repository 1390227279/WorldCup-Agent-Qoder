from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CollectionRunStatus = Literal["FETCHING", "FETCHED", "PROCESSING", "COMPLETED", "FAILED"]


class DataCollectionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    source_name: str
    source_url: str | None
    acquisition_method: str
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
    inserted_record_count: int = Field(default=0, ge=0)
    duplicate_record_count: int = Field(default=0, ge=0)
    updated_team_count: int = Field(ge=0)
    skipped_team_count: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)
    message: str

class DataCollectionChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; run_id: int; record_type: str; team_id: int | None; fifa_code: str | None
    field_name: str | None; old_value: str | None; new_value: str | None
    change_status: str; source_index: int | None; error_message: str | None; created_at: datetime
