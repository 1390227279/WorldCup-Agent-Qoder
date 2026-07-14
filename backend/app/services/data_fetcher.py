"""Asynchronous extract-and-trace service for immutable raw snapshots."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_collection import DataCollectionRun
from app.services.data_source_registry import FetchSource, get_fetch_source


DEFAULT_SNAPSHOT_ROOT = Path(__file__).resolve().parent.parent / "resources" / "snapshots"
MAX_SNAPSHOT_BYTES = 20 * 1024 * 1024


class DataFetchError(RuntimeError):
    def __init__(self, message: str, run_id: int | None = None) -> None:
        self.run_id = run_id
        super().__init__(message)


class DataFetcherService:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        snapshot_root: Path | None = None,
        max_snapshot_bytes: int = MAX_SNAPSHOT_BYTES,
    ) -> None:
        self._client = client
        self.snapshot_root = (snapshot_root or DEFAULT_SNAPSHOT_ROOT).resolve()
        self.max_snapshot_bytes = max_snapshot_bytes

    async def fetch(self, source_id: str, db: AsyncSession) -> DataCollectionRun:
        source = get_fetch_source(source_id)
        if source is None:
            raise DataFetchError(f"未知或未授权的数据源：{source_id}")

        run = DataCollectionRun(
            source_name=source.name,
            source_url=source.url,
            status="FETCHING",
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        try:
            response = await self._request(source)
            run.http_status = response.status_code
            response.raise_for_status()
            content = response.content
            if not content:
                raise ValueError("外部数据源返回了空响应")
            if len(content) > self.max_snapshot_bytes:
                raise ValueError(f"响应体超过允许上限 {self.max_snapshot_bytes} 字节")
            self._validate_content_type(source, response.headers.get("content-type", ""))

            final_path = self._persist_snapshot(source.name, content)
            persisted = final_path.read_bytes()
            run.snapshot_path = f"resources/snapshots/{final_path.name}"
            run.snapshot_bytes = len(persisted)
            run.sha256_hash = hashlib.sha256(persisted).hexdigest()
            run.status = "FETCHED"
            run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            run.error_message = None
            await db.commit()
            await db.refresh(run)
            return run
        except Exception as exc:
            if isinstance(exc, httpx.HTTPStatusError):
                run.http_status = exc.response.status_code
            run.status = "FAILED"
            run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            run.error_message = str(exc)[:2000]
            await db.commit()
            await db.refresh(run)
            raise DataFetchError(f"数据抓取失败：{run.error_message}", run.id) from exc

    async def _request(self, source: FetchSource) -> httpx.Response:
        headers = {"User-Agent": "WorldCup-Agent-Qoder/2.0 data-lineage"}
        if self._client is not None:
            return await self._client.get(source.url, headers=headers)
        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, max_redirects=3) as client:
            return await client.get(source.url, headers=headers)

    @staticmethod
    def _validate_content_type(source: FetchSource, content_type: str) -> None:
        normalized = content_type.lower().split(";", 1)[0].strip()
        if normalized and normalized not in source.expected_content_types:
            raise ValueError(f"响应类型不符合预期：{normalized}")

    def _persist_snapshot(self, source_name: str, content: bytes) -> Path:
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        short_hash = hashlib.sha256(content).hexdigest()[:8]
        final_path = (self.snapshot_root / f"{timestamp}_{source_name}_{short_hash}_raw.json").resolve()
        if final_path.parent != self.snapshot_root:
            raise ValueError("快照路径越过了受控目录")
        temporary_path = self.snapshot_root / f".{uuid4().hex}.tmp"
        try:
            temporary_path.write_bytes(content)
            os.replace(temporary_path, final_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return final_path
