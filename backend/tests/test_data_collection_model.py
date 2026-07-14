from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, DataCollectionRun
from app.schema.data_collection_schema import DataCollectionRunResponse


def test_data_collection_run_round_trips_through_response_contract():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run = DataCollectionRun(
            source_name="openfootball",
            source_url="https://example.test/data.json",
            status="FAILED",
            http_status=503,
            started_at=datetime(2026, 7, 14, 12, 0, 0),
            completed_at=datetime(2026, 7, 14, 12, 0, 1),
            updated_team_count=0,
            error_message="外部服务暂时不可用",
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        response = DataCollectionRunResponse.model_validate(run)
        assert response.id == run.id
        assert response.status == "FAILED"
        assert response.updated_team_count == 0
        assert response.error_message == "外部服务暂时不可用"
