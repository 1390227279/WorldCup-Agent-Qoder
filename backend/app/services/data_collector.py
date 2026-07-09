"""
Data Collector — gathers World Cup data from multiple sources.

Data sources:
1. Built-in historical dataset (curated key matches for ELO calibration)
2. FIFA rankings (web fetch from fifa.com or cached JSON)
3. Tournament structure fixtures (static JSON for 2026 format)

All data flows through DataProcessor for cleaning and normalization
before being stored in the database.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ── Data Structures ─────────────────────────────────────────

@dataclass
class HistoricalMatch:
    """A single historical match record."""
    date: str                          # "2022-12-18"
    tournament: str                    # "World Cup 2022"
    stage: str                         # "FINAL" / "GROUP" / "QF" etc.
    home_team: str                     # FIFA code e.g. "ARG"
    away_team: str
    home_goals: int
    away_goals: int
    is_neutral: bool = True
    is_knockout: bool = False


@dataclass
class FifaRanking:
    """FIFA ranking entry for a single team."""
    fifa_code: str
    rank: int
    points: float
    rank_date: str                     # "2026-06-18"


@dataclass
class CollectedData:
    """Container for all collected raw data."""
    historical_matches: list[HistoricalMatch] = field(default_factory=list)
    fifa_rankings: list[FifaRanking] = field(default_factory=list)
    source_stats: dict[str, int] = field(default_factory=dict)  # source → record count


# ── Built-in Historical Dataset ─────────────────────────────
#
# These are key World Cup matches from recent tournaments.
# Used to calibrate the ELO model and provide "historical record"
# for the Agent's get_h2h_record tool.
#
# Data curated from FIFA official records and Wikipedia.

BUILTIN_HISTORICAL_MATCHES: list[HistoricalMatch] = [
    # ── World Cup 2022 ──
    HistoricalMatch("2022-12-18", "World Cup 2022", "FINAL", "ARG", "FRA", 3, 3, True, True),
    HistoricalMatch("2022-12-17", "World Cup 2022", "THIRD", "CRO", "MAR", 2, 1, True, True),
    HistoricalMatch("2022-12-13", "World Cup 2022", "SF", "ARG", "CRO", 3, 0, True, True),
    HistoricalMatch("2022-12-14", "World Cup 2022", "SF", "FRA", "MAR", 2, 0, True, True),
    HistoricalMatch("2022-12-09", "World Cup 2022", "QF", "CRO", "BRA", 1, 1, True, True),
    HistoricalMatch("2022-12-09", "World Cup 2022", "QF", "NED", "ARG", 2, 2, True, True),
    HistoricalMatch("2022-12-10", "World Cup 2022", "QF", "MAR", "POR", 1, 0, True, True),
    HistoricalMatch("2022-12-10", "World Cup 2022", "QF", "ENG", "FRA", 1, 2, True, True),
    HistoricalMatch("2022-12-04", "World Cup 2022", "R16", "FRA", "POL", 3, 1, True, True),
    HistoricalMatch("2022-12-04", "World Cup 2022", "R16", "ENG", "SEN", 3, 0, True, True),
    HistoricalMatch("2022-12-05", "World Cup 2022", "R16", "JPN", "CRO", 1, 1, True, True),
    HistoricalMatch("2022-12-05", "World Cup 2022", "R16", "BRA", "KOR", 4, 1, True, True),
    HistoricalMatch("2022-12-06", "World Cup 2022", "R16", "MAR", "ESP", 0, 0, True, True),
    HistoricalMatch("2022-12-06", "World Cup 2022", "R16", "POR", "SUI", 6, 1, True, True),
    HistoricalMatch("2022-12-03", "World Cup 2022", "R16", "NED", "USA", 3, 1, True, True),
    HistoricalMatch("2022-12-03", "World Cup 2022", "R16", "ARG", "AUS", 2, 1, True, True),

    # Key 2022 Group Stage matches
    HistoricalMatch("2022-11-22", "World Cup 2022", "GROUP", "ARG", "KSA", 1, 2, True, False),
    HistoricalMatch("2022-11-23", "World Cup 2022", "GROUP", "GER", "JPN", 1, 2, True, False),
    HistoricalMatch("2022-11-23", "World Cup 2022", "GROUP", "ESP", "CRC", 7, 0, True, False),
    HistoricalMatch("2022-11-24", "World Cup 2022", "GROUP", "BRA", "SRB", 2, 0, True, False),
    HistoricalMatch("2022-11-25", "World Cup 2022", "GROUP", "ENG", "USA", 0, 0, True, False),
    HistoricalMatch("2022-11-26", "World Cup 2022", "GROUP", "FRA", "DEN", 2, 1, True, False),
    HistoricalMatch("2022-11-27", "World Cup 2022", "GROUP", "ESP", "GER", 1, 1, True, False),
    HistoricalMatch("2022-11-28", "World Cup 2022", "GROUP", "BRA", "SUI", 1, 0, True, False),
    HistoricalMatch("2022-11-29", "World Cup 2022", "GROUP", "NED", "QAT", 2, 0, True, False),

    # ── World Cup 2018 ──
    HistoricalMatch("2018-07-15", "World Cup 2018", "FINAL", "FRA", "CRO", 4, 2, True, True),
    HistoricalMatch("2018-07-14", "World Cup 2018", "THIRD", "BEL", "ENG", 2, 0, True, True),
    HistoricalMatch("2018-07-10", "World Cup 2018", "SF", "FRA", "BEL", 1, 0, True, True),
    HistoricalMatch("2018-07-11", "World Cup 2018", "SF", "CRO", "ENG", 2, 1, True, True),
    HistoricalMatch("2018-07-06", "World Cup 2018", "QF", "FRA", "URU", 2, 0, True, True),
    HistoricalMatch("2018-07-06", "World Cup 2018", "QF", "BRA", "BEL", 1, 2, True, True),
    HistoricalMatch("2018-07-07", "World Cup 2018", "QF", "ENG", "SWE", 2, 0, True, True),
    HistoricalMatch("2018-07-07", "World Cup 2018", "QF", "CRO", "RUS", 2, 2, True, True),
    HistoricalMatch("2018-06-30", "World Cup 2018", "R16", "FRA", "ARG", 4, 3, True, True),
    HistoricalMatch("2018-06-30", "World Cup 2018", "R16", "URU", "POR", 2, 1, True, True),
    HistoricalMatch("2018-07-01", "World Cup 2018", "R16", "CRO", "DEN", 1, 1, True, True),
    HistoricalMatch("2018-07-02", "World Cup 2018", "R16", "BEL", "JPN", 3, 2, True, True),
    HistoricalMatch("2018-07-02", "World Cup 2018", "R16", "BRA", "MEX", 2, 0, True, True),

    # ── World Cup 2014 ──
    HistoricalMatch("2014-07-13", "World Cup 2014", "FINAL", "GER", "ARG", 1, 0, True, True),
    HistoricalMatch("2014-07-08", "World Cup 2014", "SF", "BRA", "GER", 1, 7, True, True),
    HistoricalMatch("2014-07-09", "World Cup 2014", "SF", "NED", "ARG", 0, 0, True, True),
    HistoricalMatch("2014-07-04", "World Cup 2014", "QF", "FRA", "GER", 0, 1, True, True),
    HistoricalMatch("2014-07-04", "World Cup 2014", "QF", "BRA", "COL", 2, 1, True, True),
    HistoricalMatch("2014-07-05", "World Cup 2014", "QF", "ARG", "BEL", 1, 0, True, True),
    HistoricalMatch("2014-07-05", "World Cup 2014", "QF", "NED", "CRC", 0, 0, True, True),

    # ── World Cup 2010 ──
    HistoricalMatch("2010-07-11", "World Cup 2010", "FINAL", "NED", "ESP", 0, 1, True, True),
    HistoricalMatch("2010-07-07", "World Cup 2010", "SF", "GER", "ESP", 0, 1, True, True),
    HistoricalMatch("2010-07-06", "World Cup 2010", "SF", "URU", "NED", 2, 3, True, True),

    # ── Key friendlies / recent competitive matches (2023-2026) ──
    HistoricalMatch("2024-07-14", "Copa America 2024", "FINAL", "ARG", "COL", 1, 0, True, True),
    HistoricalMatch("2024-07-06", "Copa America 2024", "QF", "BRA", "URU", 0, 0, True, True),
    HistoricalMatch("2024-06-29", "Copa America 2024", "GROUP", "ARG", "PER", 2, 0, True, False),
    HistoricalMatch("2024-07-09", "Euro 2024", "SF", "ESP", "FRA", 2, 1, True, True),
    HistoricalMatch("2024-07-10", "Euro 2024", "SF", "NED", "ENG", 1, 2, True, True),
    HistoricalMatch("2024-07-14", "Euro 2024", "FINAL", "ESP", "ENG", 2, 1, True, True),
    HistoricalMatch("2024-07-06", "Euro 2024", "QF", "ENG", "SUI", 1, 1, True, True),
    HistoricalMatch("2024-07-06", "Euro 2024", "QF", "NED", "TUR", 2, 1, True, True),
    HistoricalMatch("2024-07-05", "Euro 2024", "QF", "ESP", "GER", 2, 1, True, True),
    HistoricalMatch("2024-07-05", "Euro 2024", "QF", "POR", "FRA", 0, 0, True, True),
    HistoricalMatch("2025-06-08", "Nations League 2025", "FINAL", "ESP", "NED", 1, 1, True, True),
    HistoricalMatch("2025-06-04", "Nations League 2025", "SF", "FRA", "ESP", 0, 2, True, True),
    HistoricalMatch("2025-03-23", "WCQ 2026", "QF", "BRA", "ARG", 0, 1, True, False),
    HistoricalMatch("2025-03-25", "WCQ 2026", "QF", "URU", "ARG", 1, 0, True, False),
    HistoricalMatch("2026-03-20", "Friendly", "Friendly", "GER", "ITA", 3, 3, True, False),
    HistoricalMatch("2026-03-25", "Friendly", "Friendly", "ENG", "BRA", 1, 0, True, False),
    HistoricalMatch("2026-03-26", "Friendly", "Friendly", "FRA", "ESP", 2, 2, True, False),
]

# ── FIFA Rankings (latest available, ~June 2026) ────────────
# These would be fetched from FIFA API in production.
# For the demo, we use curated data.

BUILTIN_FIFA_RANKINGS: list[FifaRanking] = [
    FifaRanking("ARG", 1, 2100.0, "2026-06-18"),
    FifaRanking("FRA", 2, 2085.0, "2026-06-18"),
    FifaRanking("BRA", 3, 2075.0, "2026-06-18"),
    FifaRanking("ENG", 4, 2064.0, "2026-06-18"),
    FifaRanking("ESP", 5, 2044.0, "2026-06-18"),
    FifaRanking("NED", 6, 2031.0, "2026-06-18"),
    FifaRanking("BEL", 7, 2005.0, "2026-06-18"),
    FifaRanking("POR", 8, 1994.0, "2026-06-18"),
    FifaRanking("ITA", 9, 1986.0, "2026-06-18"),
    FifaRanking("CRO", 10, 1974.0, "2026-06-18"),
    FifaRanking("USA", 11, 1960.0, "2026-06-18"),
    FifaRanking("MEX", 12, 1915.0, "2026-06-18"),
    FifaRanking("MAR", 13, 1901.0, "2026-06-18"),
    FifaRanking("URU", 14, 1895.0, "2026-06-18"),
    FifaRanking("GER", 15, 1888.0, "2026-06-18"),
    FifaRanking("SUI", 16, 1872.0, "2026-06-18"),
    FifaRanking("JPN", 17, 1860.0, "2026-06-18"),
    FifaRanking("SEN", 18, 1845.0, "2026-06-18"),
    FifaRanking("COL", 19, 1836.0, "2026-06-18"),
    FifaRanking("DEN", 20, 1828.0, "2026-06-18"),
    FifaRanking("IRN", 22, 1800.0, "2026-06-18"),
    FifaRanking("KOR", 23, 1790.0, "2026-06-18"),
    FifaRanking("SWE", 24, 1775.0, "2026-06-18"),
    FifaRanking("SRB", 25, 1760.0, "2026-06-18"),
    FifaRanking("AUT", 26, 1748.0, "2026-06-18"),
    FifaRanking("AUS", 27, 1740.0, "2026-06-18"),
    FifaRanking("POL", 28, 1725.0, "2026-06-18"),
    FifaRanking("UKR", 29, 1710.0, "2026-06-18"),
    FifaRanking("ALG", 30, 1695.0, "2026-06-18"),
    FifaRanking("NGA", 31, 1680.0, "2026-06-18"),
    FifaRanking("ECU", 32, 1670.0, "2026-06-18"),
    FifaRanking("EGY", 33, 1655.0, "2026-06-18"),
    FifaRanking("PER", 34, 1645.0, "2026-06-18"),
    FifaRanking("TUN", 35, 1630.0, "2026-06-18"),
    FifaRanking("HUN", 36, 1620.0, "2026-06-18"),
    FifaRanking("QAT", 37, 1610.0, "2026-06-18"),
    FifaRanking("CAN", 42, 1560.0, "2026-06-18"),
    FifaRanking("NOR", 43, 1550.0, "2026-06-18"),
    FifaRanking("CHI", 44, 1540.0, "2026-06-18"),
    FifaRanking("CMR", 45, 1525.0, "2026-06-18"),
    FifaRanking("MLI", 47, 1500.0, "2026-06-18"),
    FifaRanking("CRC", 49, 1485.0, "2026-06-18"),
    FifaRanking("PAR", 50, 1470.0, "2026-06-18"),
    FifaRanking("KSA", 53, 1430.0, "2026-06-18"),
    FifaRanking("GHA", 60, 1390.0, "2026-06-18"),
    FifaRanking("RSA", 62, 1375.0, "2026-06-18"),
    FifaRanking("CHN", 80, 1270.0, "2026-06-18"),
    FifaRanking("NZL", 103, 1160.0, "2026-06-18"),
]


# ── Data Collector ──────────────────────────────────────────

class DataCollector:
    """
    Collects all data from configured sources.

    Usage:
        collector = DataCollector()
        data = collector.collect_all()
        # data.historical_matches → list[HistoricalMatch]
        # data.fifa_rankings → list[FifaRanking]
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path(__file__).parent.parent.parent / "data"
        self.raw_dir = self.data_dir / "raw"

    def collect_all(self) -> CollectedData:
        """Gather data from all sources."""
        data = CollectedData()

        # Source 1: Built-in historical matches
        data.historical_matches.extend(self._collect_builtin_history())
        data.source_stats["builtin_history"] = len(data.historical_matches)

        # Source 2: Built-in FIFA rankings
        data.fifa_rankings.extend(self._collect_builtin_rankings())
        data.source_stats["builtin_rankings"] = len(data.fifa_rankings)

        # Source 3: External files (if present)
        external = self._collect_external_files()
        if external.historical_matches:
            data.historical_matches.extend(external.historical_matches)
            data.source_stats["external_csv"] = len(external.historical_matches)
        if external.fifa_rankings:
            data.fifa_rankings.extend(external.fifa_rankings)
            data.source_stats["external_rankings"] = len(external.fifa_rankings)

        return data

    def _collect_builtin_history(self) -> list[HistoricalMatch]:
        return list(BUILTIN_HISTORICAL_MATCHES)

    def _collect_builtin_rankings(self) -> list[FifaRanking]:
        return list(BUILTIN_FIFA_RANKINGS)

    def _collect_external_files(self) -> CollectedData:
        """Try to load additional data from CSV/JSON files in data/raw/."""
        data = CollectedData()
        # Reserve for future: load kaggle CSV, FIFA JSON, etc.
        return data
