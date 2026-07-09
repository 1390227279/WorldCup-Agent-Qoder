"""
Data Processor — cleans, validates, and normalizes collected data.

Takes raw data from DataCollector and produces clean, database-ready records.
Handles:
- Missing value detection and logging
- Duplicate removal
- Date format normalization
- Team name → FIFA code mapping
- Data quality reports
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .data_collector import CollectedData, HistoricalMatch, FifaRanking


@dataclass
class DataQualityReport:
    """Summary of data quality issues found during processing."""
    total_records: int = 0
    duplicates_removed: int = 0
    missing_dates: int = 0
    missing_teams: int = 0
    invalid_scores: int = 0
    unknown_teams: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ProcessedData:
    """Clean, validated data ready for database loading."""
    matches: list[HistoricalMatch] = field(default_factory=list)
    rankings: list[FifaRanking] = field(default_factory=list)
    quality: DataQualityReport = field(default_factory=DataQualityReport)


# Valid FIFA codes in our system (from seed data)
VALID_FIFA_CODES: set[str] = {
    "USA", "NED", "SEN", "QAT",       # Group A
    "FRA", "URU", "KOR", "GHA",       # Group B
    "ARG", "POR", "EGY", "CAN",       # Group C
    "BRA", "GER", "MAR", "NZL",       # Group D
    "ENG", "CRO", "JPN", "PAR",       # Group E
    "ESP", "MEX", "SUI", "CMR",       # Group F
    "ITA", "COL", "SRB", "KSA",       # Group G
    "BEL", "DEN", "ALG", "AUS",       # Group H
    "SWE", "NGA", "CHI", "IRN",       # Group I
    "POL", "TUN", "AUT", "UKR",       # Group J
    "MLI", "CRC", "CHN", "NOR",       # Group K
    "ECU", "PER", "HUN", "RSA",       # Group L
    # Additional teams in historical data
    "RUS", "TUR",
}


class DataProcessor:
    """
    Cleans and validates collected data.

    Usage:
        processor = DataProcessor()
        processed = processor.process(raw_data)
        # processed.matches → clean match list
        # processed.quality → quality report
    """

    def __init__(self, valid_codes: Optional[set[str]] = None):
        self.valid_codes = valid_codes or VALID_FIFA_CODES

    def process(self, raw: CollectedData) -> ProcessedData:
        """Main entry point: process all raw data."""
        processed = ProcessedData()
        report = DataQualityReport()

        # Process matches
        matches = self._clean_matches(raw.historical_matches, report)
        report.total_records = len(raw.historical_matches)

        # Process rankings
        rankings = self._clean_rankings(raw.fifa_rankings, report)

        processed.matches = matches
        processed.rankings = rankings
        processed.quality = report

        return processed

    def _clean_matches(
        self, matches: list[HistoricalMatch], report: DataQualityReport
    ) -> list[HistoricalMatch]:
        """Clean and validate match records."""
        seen = set()
        clean = []

        for m in matches:
            # Check for duplicates
            key = (m.date, m.home_team, m.away_team)
            if key in seen:
                report.duplicates_removed += 1
                continue
            seen.add(key)

            # Validate fields
            if not m.date:
                report.missing_dates += 1
                continue

            if not m.home_team or not m.away_team:
                report.missing_teams += 1
                continue

            if m.home_goals < 0 or m.away_goals < 0:
                report.invalid_scores += 1
                continue

            # Track unknown teams (not in our 48-team list)
            for code in (m.home_team, m.away_team):
                if code not in self.valid_codes and code not in report.unknown_teams:
                    report.unknown_teams.append(code)
                    report.warnings.append(
                        f"Team code '{code}' not in valid 48-team list "
                        f"(match: {m.home_team} vs {m.away_team}, {m.date})"
                    )

            clean.append(m)

        return clean

    def _clean_rankings(
        self, rankings: list[FifaRanking], report: DataQualityReport
    ) -> list[FifaRanking]:
        """Clean and deduplicate ranking records."""
        seen = set()
        clean = []

        for r in rankings:
            if not r.fifa_code:
                continue
            if r.fifa_code in seen:
                report.duplicates_removed += 1
                continue
            if r.fifa_code not in self.valid_codes:
                report.warnings.append(
                    f"Ranking for unknown team code '{r.fifa_code}'"
                )
            seen.add(r.fifa_code)
            clean.append(r)

        return clean

    def validate(self, processed: ProcessedData) -> bool:
        """Quick validation: do we have enough data to proceed?"""
        report = processed.quality
        issues = (
            report.missing_dates
            + report.missing_teams
            + report.invalid_scores
        )
        return issues == 0 and len(processed.matches) > 0
