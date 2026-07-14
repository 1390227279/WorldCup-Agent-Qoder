import hashlib
import json
from datetime import date

import pytest

from app.models.data_collection import DataCollectionRun
from app.services.data_parser import (
    DataParseError,
    DataParserService,
    HistoricalMatchRecord,
    TeamEloJsonParser,
    TeamMetricRecord,
)


def _fetched_run(app_root, payload: bytes, source_name: str = "openfootball"):
    snapshot_dir = app_root / "resources" / "snapshots"
    snapshot_dir.mkdir(parents=True)
    snapshot = snapshot_dir / "verified_raw.json"
    snapshot.write_bytes(payload)
    return DataCollectionRun(
        id=1,
        source_name=source_name,
        status="FETCHED",
        snapshot_path="resources/snapshots/verified_raw.json",
        snapshot_bytes=len(payload),
        sha256_hash=hashlib.sha256(payload).hexdigest(),
        raw_record_count=0,
        updated_team_count=0,
        skipped_team_count=0,
    ), snapshot


def test_openfootball_parser_normalizes_matches_and_reports_bad_rows(tmp_path):
    payload = json.dumps({
        "name": "World Cup 2022",
        "matches": [
            {"round": "Final", "date": "2022-12-18", "team1": "ARG", "team2": "FRA", "score": {"ft": [3, 3]}},
            {"round": "Group", "date": "2022-11-20", "team1": "QAT", "team2": "ECU", "score": {}},
        ],
    }).encode()
    run, _ = _fetched_run(tmp_path, payload)

    result = DataParserService(app_root=tmp_path).parse_run(run)

    assert result.raw_record_count == 2
    assert result.skipped_record_count == 1
    assert len(result.errors) == 1
    assert result.records == [HistoricalMatchRecord(
        source_index=1,
        match_date=date(2022, 12, 18),
        tournament="World Cup 2022",
        stage="Final",
        home_fifa_code="ARG",
        away_fifa_code="FRA",
        home_goals=3,
        away_goals=3,
    )]


def test_openfootball_parser_supports_worldcup_json_rounds_structure(tmp_path):
    payload = json.dumps({
        "name": "World Cup 2022",
        "rounds": [{
            "name": "Final",
            "matches": [{
                "date": "2022-12-18",
                "team1": {"name": "Argentina", "code": "ARG"},
                "team2": {"name": "France", "code": "FRA"},
                "score": {"ft": [3, 3], "p": [4, 2]},
            }],
        }],
    }).encode()
    run, _ = _fetched_run(tmp_path, payload)

    result = DataParserService(app_root=tmp_path).parse_run(run)

    assert result.raw_record_count == 1
    assert result.skipped_record_count == 0
    assert result.records[0].stage == "Final"
    assert result.records[0].home_fifa_code == "ARG"
    assert result.records[0].away_fifa_code == "FRA"


def test_openfootball_parser_maps_full_team_names_to_fifa_codes(tmp_path):
    payload = json.dumps({"matches": [
        {"date": "2022-11-20", "team1": "Qatar", "team2": "Ecuador", "score": {"ft": [0, 2]}},
        {"date": "2022-12-02", "team1": "South Korea", "team2": "Portugal", "score": {"ft": [2, 1]}},
    ]}).encode()
    run, _ = _fetched_run(tmp_path, payload)
    result = DataParserService(app_root=tmp_path).parse_run(run)
    assert [(item.home_fifa_code, item.away_fifa_code) for item in result.records] == [
        ("QAT", "ECU"), ("KOR", "POR"),
    ]
    assert result.skipped_record_count == 0


def test_parser_rejects_tampered_snapshot(tmp_path):
    run, snapshot = _fetched_run(tmp_path, b'{"matches": []}')
    snapshot.write_bytes(b'{"matches": ["tampered"]}')

    with pytest.raises(DataParseError, match="快照大小|SHA-256"):
        DataParserService(app_root=tmp_path).parse_run(run)


def test_parser_rejects_non_fetched_run_and_path_escape(tmp_path):
    run, _ = _fetched_run(tmp_path, b'{"matches": []}')
    run.status = "FAILED"
    with pytest.raises(DataParseError, match="只有 FETCHED"):
        DataParserService(app_root=tmp_path).parse_run(run)

    run.status = "FETCHED"
    run.snapshot_path = "../outside.json"
    with pytest.raises(DataParseError, match="越过"):
        DataParserService(app_root=tmp_path).parse_run(run)


def test_elo_parser_validates_codes_ranges_and_effective_date():
    payload = json.dumps({"teams": [
        {"fifa_code": "ARG", "elo": 2102.5, "effective_at": "2026-07-14"},
        {"fifa_code": "BADCODE", "elo": 1900},
        {"fifa_code": "FRA", "elo": 9999},
    ]}).encode()

    result = TeamEloJsonParser().parse(payload)

    assert result.raw_record_count == 3
    assert result.skipped_record_count == 2
    assert result.records == [TeamMetricRecord(
        source_index=1,
        fifa_code="ARG",
        metric_type="ELO",
        value=2102.5,
        effective_at=date(2026, 7, 14),
    )]


def test_openfootball_snapshot_never_produces_elo_metrics(tmp_path):
    payload = json.dumps({
        "matches": [{"date": "2022-12-18", "team1": "ARG", "team2": "FRA", "score": {"ft": [3, 3]}}]
    }).encode()
    run, _ = _fetched_run(tmp_path, payload)

    result = DataParserService(app_root=tmp_path).parse_run(run)

    assert all(isinstance(record, HistoricalMatchRecord) for record in result.records)
    assert not any(isinstance(record, TeamMetricRecord) for record in result.records)
