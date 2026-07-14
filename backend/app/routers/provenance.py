from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_collection import DataCollectionRun
from app.models.database import get_db
from app.schema.data_collection_schema import (
    DataCollectionRunResponse,
    DataCollectionProcessResponse,
    DataCollectionSourceResponse,
)
from app.schema.provenance_schema import DataProvenanceResponse
from app.services.data_fetcher import DataFetchError, DataFetcherService
from app.services.data_loader import DataLoadError, DataLoaderService
from app.services.data_parser import DataParseError, DataParserService
from app.services.data_provenance import get_data_provenance
from app.services.data_source_registry import FETCH_SOURCES

router = APIRouter()


@router.get("", response_model=DataProvenanceResponse)
async def list_data_sources():
    return get_data_provenance()


@router.get("/fetch-sources", response_model=list[DataCollectionSourceResponse])
async def list_fetch_sources():
    return [
        DataCollectionSourceResponse(id=item.id, name=item.name, url=item.url)
        for item in FETCH_SOURCES.values()
    ]


@router.get("/collection-runs", response_model=list[DataCollectionRunResponse])
async def list_collection_runs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DataCollectionRun).order_by(DataCollectionRun.id.desc()).limit(limit)
    )
    return list(result.scalars())


@router.post("/collect/{source_id}", response_model=DataCollectionRunResponse)
async def collect_source(source_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await DataFetcherService().fetch(source_id, db)
    except DataFetchError as exc:
        status_code = 404 if exc.run_id is None else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/process/{run_id}", response_model=DataCollectionProcessResponse)
async def process_collected_data(run_id: int, db: AsyncSession = Depends(get_db)):
    """Parse a FETCHED snapshot and load its validated metrics into the teams table."""
    run = await db.get(DataCollectionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"采集运行 ID={run_id} 不存在")

    try:
        snapshot = DataParserService().parse_run(run)
        load_result = await DataLoaderService().load_metrics(run, snapshot, db)
    except DataParseError as exc:
        run.status = "FAILED"
        run.error_message = f"解析失败：{exc}"[:2000]
        run.completed_at = None
        await db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DataLoadError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return DataCollectionProcessResponse(
        run_id=run.id,
        status=run.status,
        raw_record_count=run.raw_record_count,
        updated_team_count=load_result.updated_team_count,
        skipped_team_count=load_result.skipped_team_count,
        errors=load_result.errors,
        message=(
            f"成功更新 {load_result.updated_team_count} 支球队的 ELO 评分"
            if load_result.updated_team_count > 0
            else "未更新任何球队 — 检查错误详情"
        ),
    )
