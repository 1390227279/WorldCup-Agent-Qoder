from typing import Literal

from pydantic import BaseModel, ConfigDict


class DataSourceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    category: str
    provider: str
    source_url: str | None
    local_path: str | None
    acquisition_method: str
    verification_status: Literal["VERIFIED_LOCAL", "PENDING_NETWORK_REFRESH"]
    used_by: list[str]
    is_official: bool
    notice: str
    snapshot_sha256: str | None = None
    snapshot_bytes: int | None = None
    record_count: int | None = None
    snapshot_modified_at: str | None = None


class DataProvenanceResponse(BaseModel):
    manifest_version: str
    generated_at: str
    transparency_notice: str
    verified_local_sources: int
    pending_network_sources: int
    sources: list[DataSourceEvidence]
