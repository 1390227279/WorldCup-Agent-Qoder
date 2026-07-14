"""Source-specific parsers that transform verified snapshots into normalized records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

from app.models.data_collection import DataCollectionRun


APP_ROOT = Path(__file__).resolve().parent.parent


class DataParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HistoricalMatchRecord:
    source_index: int
    match_date: date
    tournament: str
    stage: str
    home_fifa_code: str
    away_fifa_code: str
    home_goals: int
    away_goals: int


@dataclass(frozen=True, slots=True)
class TeamMetricRecord:
    source_index: int
    fifa_code: str
    metric_type: str
    value: float
    effective_at: date | None = None


@dataclass(slots=True)
class ParsedSnapshot:
    source_name: str
    raw_record_count: int
    records: list[HistoricalMatchRecord | TeamMetricRecord] = field(default_factory=list)
    skipped_record_count: int = 0
    errors: list[str] = field(default_factory=list)


class SnapshotParser(Protocol):
    def parse(self, content: bytes) -> ParsedSnapshot: ...


class OpenFootballWorldCupParser:
    """Parse openfootball match JSON as history; it does not manufacture ELO values."""

    source_name = "openfootball"
    TEAM_NAME_TO_FIFA_CODE = {
        "argentina": "ARG", "australia": "AUS", "belgium": "BEL",
        "brazil": "BRA", "cameroon": "CMR", "canada": "CAN",
        "costa rica": "CRC", "croatia": "CRO", "denmark": "DEN",
        "ecuador": "ECU", "england": "ENG", "france": "FRA",
        "germany": "GER", "ghana": "GHA", "iran": "IRN",
        "japan": "JPN", "mexico": "MEX", "morocco": "MAR",
        "netherlands": "NED", "poland": "POL", "portugal": "POR",
        "qatar": "QAT", "saudi arabia": "KSA", "senegal": "SEN",
        "serbia": "SRB", "south korea": "KOR", "spain": "ESP",
        "switzerland": "SUI", "tunisia": "TUN", "uruguay": "URU",
        "usa": "USA", "united states": "USA", "wales": "WAL",
    }

    def parse(self, content: bytes) -> ParsedSnapshot:
        try:
            payload = json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DataParseError(f"openfootball 快照不是有效 UTF-8 JSON：{exc}") from exc
        if not isinstance(payload, dict):
            raise DataParseError("openfootball 快照顶层必须是对象")
        matches = self._extract_matches(payload)
        if not matches:
            raise DataParseError("openfootball 快照未找到 matches 或 rounds[].matches")
        result = ParsedSnapshot(source_name=self.source_name, raw_record_count=len(matches))
        tournament = str(payload.get("name") or "World Cup").strip()
        for index, (item, parent_round) in enumerate(matches, start=1):
            try:
                if not isinstance(item, dict):
                    raise ValueError("记录不是对象")
                home_code = self._team_code(item.get("team1") or item.get("home"))
                away_code = self._team_code(item.get("team2") or item.get("away"))
                home_goals, away_goals = self._full_time_score(item.get("score"))
                match_date = date.fromisoformat(str(item.get("date", ""))[:10])
                stage = str(item.get("round") or item.get("group") or parent_round or "UNKNOWN").strip()
                result.records.append(HistoricalMatchRecord(
                    source_index=index,
                    match_date=match_date,
                    tournament=tournament,
                    stage=stage,
                    home_fifa_code=home_code,
                    away_fifa_code=away_code,
                    home_goals=home_goals,
                    away_goals=away_goals,
                ))
            except (TypeError, ValueError) as exc:
                result.skipped_record_count += 1
                result.errors.append(f"第 {index} 条比赛记录：{exc}")
        return result

    @staticmethod
    def _extract_matches(payload: dict) -> list[tuple[dict, str | None]]:
        direct = payload.get("matches")
        if isinstance(direct, list):
            return [(item, None) for item in direct]
        extracted: list[tuple[dict, str | None]] = []
        rounds = payload.get("rounds")
        if isinstance(rounds, list):
            for round_item in rounds:
                if not isinstance(round_item, dict) or not isinstance(round_item.get("matches"), list):
                    continue
                round_name = str(round_item.get("name") or "").strip() or None
                extracted.extend((match, round_name) for match in round_item["matches"])
        return extracted

    @staticmethod
    def _team_code(value) -> str:
        if isinstance(value, dict):
            value = value.get("code") or value.get("fifa_code") or value.get("name")
        raw = str(value or "").strip()
        mapped = OpenFootballWorldCupParser.TEAM_NAME_TO_FIFA_CODE.get(raw.casefold())
        code = mapped or raw.upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError(f"无效 FIFA code：{value!r}")
        return code

    @staticmethod
    def _full_time_score(value) -> tuple[int, int]:
        if isinstance(value, dict):
            value = value.get("ft") or value.get("full_time")
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("缺少完整的全场比分")
        home_goals, away_goals = value
        if not isinstance(home_goals, int) or not isinstance(away_goals, int):
            raise ValueError("全场比分必须是整数")
        if home_goals < 0 or away_goals < 0:
            raise ValueError("全场比分不能为负数")
        return home_goals, away_goals


class TeamEloJsonParser:
    """Parse a team ELO JSON snapshot into normalized team metrics."""

    source_name = "world_football_elo"

    def parse(self, content: bytes) -> ParsedSnapshot:
        try:
            payload = json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DataParseError(f"ELO 快照不是有效 UTF-8 JSON：{exc}") from exc
        rows = payload.get("teams") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise DataParseError("ELO 快照顶层必须是数组或包含 teams 数组")
        result = ParsedSnapshot(source_name=self.source_name, raw_record_count=len(rows))
        for index, item in enumerate(rows, start=1):
            try:
                if not isinstance(item, dict):
                    raise ValueError("记录不是对象")
                code = str(item.get("fifa_code", "")).strip().upper()
                if len(code) != 3 or not code.isalpha():
                    raise ValueError("fifa_code 无效")
                value = float(item["elo"])
                if not 800 <= value <= 2500:
                    raise ValueError("ELO 超出 800-2500 合理范围")
                effective = item.get("effective_at")
                result.records.append(TeamMetricRecord(
                    source_index=index,
                    fifa_code=code,
                    metric_type="ELO",
                    value=value,
                    effective_at=date.fromisoformat(str(effective)[:10]) if effective else None,
                ))
            except (KeyError, TypeError, ValueError) as exc:
                result.skipped_record_count += 1
                result.errors.append(f"第 {index} 条 ELO 记录：{exc}")
        return result


class DataParserService:
    def __init__(self, app_root: Path | None = None) -> None:
        self.app_root = (app_root or APP_ROOT).resolve()
        self.parsers: dict[str, SnapshotParser] = {
            "openfootball": OpenFootballWorldCupParser(),
            "world_football_elo": TeamEloJsonParser(),
            "curated_elo_baseline": TeamEloJsonParser(),
        }

    def parse_run(self, run: DataCollectionRun) -> ParsedSnapshot:
        if run.status != "FETCHED":
            raise DataParseError(f"只有 FETCHED 状态可以解析，当前状态：{run.status}")
        if not run.snapshot_path or not run.sha256_hash:
            raise DataParseError("采集记录缺少快照路径或 SHA-256")
        parser = self.parsers.get(run.source_name)
        if parser is None:
            raise DataParseError(f"没有适用于 {run.source_name} 的解析器")

        snapshot = (self.app_root / run.snapshot_path).resolve()
        snapshot_root = (self.app_root / "resources" / "snapshots").resolve()
        if snapshot.parent != snapshot_root:
            raise DataParseError("快照路径越过了受控目录")
        if not snapshot.is_file():
            raise DataParseError("快照文件不存在")
        content = snapshot.read_bytes()
        if run.snapshot_bytes is not None and len(content) != run.snapshot_bytes:
            raise DataParseError("快照大小与采集账本不一致")
        digest = hashlib.sha256(content).hexdigest()
        if digest != run.sha256_hash:
            raise DataParseError("快照 SHA-256 与采集账本不一致")
        parsed = parser.parse(content)
        if run.source_name == "curated_elo_baseline":
            parsed.source_name = run.source_name
        return parsed
