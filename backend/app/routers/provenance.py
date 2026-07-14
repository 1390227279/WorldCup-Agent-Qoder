from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_collection import DataCollectionRun
from app.models.database import get_db
from app.schema.data_collection_schema import DataCollectionRunResponse, DataCollectionSourceResponse
from app.schema.provenance_schema import DataProvenanceResponse
from app.services.data_fetcher import DataFetchError, DataFetcherService
from app.services.data_provenance import get_data_provenance
from app.services.data_source_registry import FETCH_SOURCES

router = APIRouter()


@router.get("", response_model=DataProvenanceResponse)
async def list_data_sources():
    return get_data_provenance()


@router.get("/fetch-sources", response_model=list[DataCollectionSourceResponse])
async def list_fetch_sources():
    return [DataCollectionSourceResponse(id=item.id, name=item.name, url=item.url) for item in FETCH_SOURCES.values()]


@router.get("/collection-runs", response_model=list[DataCollectionRunResponse])
async def list_collection_runs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DataCollectionRun).order_by(DataCollectionRun.id.desc()).limit(limit))
    return list(result.scalars())


@router.post("/collect/{source_id}", response_model=DataCollectionRunResponse)
async def collect_source(source_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await DataFetcherService().fetch(source_id, db)
    except DataFetchError as exc:
        status_code = 404 if exc.run_id is None else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
