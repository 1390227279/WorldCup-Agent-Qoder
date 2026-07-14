from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_collection import DataCollectionRun
from app.models.database import get_db
from app.schema.data_collection_schema import DataCollectionProcessResponse, DataCollectionRunResponse, DataCollectionSourceResponse
from app.schema.provenance_schema import DataProvenanceResponse
from app.services.data_fetcher import DataFetchError, DataFetcherService
from app.services.data_pipeline import DataPipelineService
from app.services.data_provenance import get_data_provenance
from app.services.data_source_registry import FETCH_SOURCES

router = APIRouter()

@router.get("", response_model=DataProvenanceResponse)
async def list_data_sources(): return get_data_provenance()

@router.get("/fetch-sources", response_model=list[DataCollectionSourceResponse])
async def list_fetch_sources():
    return [DataCollectionSourceResponse(id=item.id, name=item.name, url=item.url) for item in FETCH_SOURCES.values()]

@router.get("/collection-runs", response_model=list[DataCollectionRunResponse])
async def list_collection_runs(limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    return list((await db.execute(select(DataCollectionRun).order_by(DataCollectionRun.id.desc()).limit(limit))).scalars())

@router.post("/collect/{source_id}", response_model=DataCollectionRunResponse)
async def collect_source(source_id: str, db: AsyncSession = Depends(get_db)):
    try: return await DataFetcherService().fetch(source_id, db)
    except DataFetchError as exc: raise HTTPException(status_code=404 if exc.run_id is None else 502, detail=str(exc)) from exc

@router.post("/process/{run_id}", response_model=DataCollectionProcessResponse)
async def process_collected_data(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(DataCollectionRun, run_id)
    if run is None: raise HTTPException(status_code=404, detail=f"采集运行 ID={run_id} 不存在")
    try: result = await DataPipelineService().process(run, db)
    except (ValueError, OSError) as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DataCollectionProcessResponse(
        run_id=result.run_id, status=result.status, raw_record_count=result.raw_record_count,
        inserted_record_count=result.inserted_record_count, duplicate_record_count=result.duplicate_record_count,
        updated_team_count=result.updated_team_count, skipped_team_count=result.skipped_record_count,
        errors=result.errors, message=result.message,
    )
