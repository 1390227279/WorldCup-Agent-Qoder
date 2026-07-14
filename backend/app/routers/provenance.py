from fastapi import APIRouter

from app.schema.provenance_schema import DataProvenanceResponse
from app.services.data_provenance import get_data_provenance

router = APIRouter()


@router.get("", response_model=DataProvenanceResponse)
async def list_data_sources():
    return get_data_provenance()
