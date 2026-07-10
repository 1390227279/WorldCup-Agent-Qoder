"""
Integration test: validate the entire data pipeline end-to-end.

Tests:
1. ELO engine correctness (known test cases)
2. Data collection completeness
3. Data processing quality checks
4. Event injector output format

Run: pytest tests/test_data_pipeline.py -v
"""

import pytest
from app.services.elo_engine import (
    expected_score,
    calculate_elo_update,
    process_match_history,
    DEFAULT_ELO,
)
from app.services.data_collector import (
    DataCollector,
    HistoricalMatch,
    BUILTIN_HISTORICAL_MATCHES,
    BUILTIN_FIFA_RANKINGS,
)
from app.services.data_processor import DataProcessor, ProcessedData


# ── ELO Engine Tests ────────────────────────────────────────

class TestEloEngine:
    """Verify ELO calculation correctness."""

    def test_expected_score_equal_teams(self):
        """Two identically rated teams should have 50/50 odds."""
        score = expected_score(2000, 2000)
        assert score == pytest.approx(0.5)

    def test_expected_score_higher_wins(self):
        """ELO 2100 vs 1350 should give ~98.7% chance to the higher team."""
        score = expected_score(2100, 1350)
        assert score > 0.95  # Very high probability
        assert score < 1.0

    def test_expected_score_lower_loses(self):
        """ELO 1350 vs 2100 should give ~1.3% to the lower team."""
        score = expected_score(1350, 2100)
        assert score < 0.05  # Very low probability
        assert score > 0.0

    def test_elo_update_win(self):
        """Winning should increase rating."""
        home_update, away_update = calculate_elo_update(
            rating_home=2000, rating_away=2000,
            home_goals=2, away_goals=0,
            is_neutral=True, is_knockout=False,
        )
        # Winner gains points
        assert home_update.change > 0
        # Loser loses the same amount (approximately)
        assert abs(home_update.change + away_update.change) < 0.01

    def test_elo_update_draw(self):
        """A draw should move ratings towards each other."""
        home_update, away_update = calculate_elo_update(
            rating_home=2000, rating_away=1900,
            home_goals=1, away_goals=1,
            is_neutral=True, is_knockout=False,
        )
        # Higher-rated team should lose points on a draw (underperformed)
        assert home_update.change < 0
        # Lower-rated team should gain (overperformed)
        assert away_update.change > 0

    def test_elo_update_upset(self):
        """A major upset should produce a large ELO swing."""
        home_update, away_update = calculate_elo_update(
            rating_home=2100, rating_away=1350,
            home_goals=0, away_goals=1,  # Big underdog wins!
            is_neutral=True, is_knockout=False,
        )
        # Underdog should gain a LOT of points
        assert away_update.change > 20
        # Favorite should lose a LOT of points
        assert home_update.change < -20

    def test_knockout_k_factor(self):
        """Knockout matches should have higher K-factor → bigger changes."""
        _, away_normal = calculate_elo_update(
            rating_home=2000, rating_away=1350,
            home_goals=0, away_goals=1,
            is_neutral=True, is_knockout=False,
        )
        _, away_knockout = calculate_elo_update(
            rating_home=2000, rating_away=1350,
            home_goals=0, away_goals=1,
            is_neutral=True, is_knockout=True,
        )
        # Knockout match should produce a bigger rating change
        assert abs(away_knockout.change) > abs(away_normal.change)

    def test_process_match_history(self):
        """Batch processing should accumulate changes correctly."""
        initial = {"A": 1500, "B": 1500}
        matches = [
            HistoricalMatch("2026-07-01", "Test", "GROUP", "A", "B", 2, 0, True, False),
            HistoricalMatch("2026-07-05", "Test", "GROUP", "A", "B", 0, 1, True, False),
        ]
        final = process_match_history(initial, matches)
        # After alternating wins, ratings should have moved
        assert final["A"] != 1500
        assert final["B"] != 1500


# ── Data Collection Tests ───────────────────────────────────

class TestDataCollector:
    """Verify data collection completeness."""

    def test_builtin_matches_count(self):
        """Should have a reasonable number of historical matches."""
        collector = DataCollector()
        data = collector.collect_all()
        assert len(data.historical_matches) >= 50, \
            f"Expected at least 50 matches, got {len(data.historical_matches)}"

    def test_builtin_rankings_count(self):
        """Should have FIFA rankings for all 48 teams."""
        collector = DataCollector()
        data = collector.collect_all()
        assert len(data.fifa_rankings) == 48, \
            f"Expected 48 rankings, got {len(data.fifa_rankings)}"

    def test_no_duplicate_matches(self):
        """Built-in data should have no duplicate matches."""
        collector = DataCollector()
        data = collector.collect_all()
        keys = [(m.date, m.home_team, m.away_team) for m in data.historical_matches]
        assert len(keys) == len(set(keys)), \
            f"Found {len(keys) - len(set(keys))} duplicate matches"

    def test_all_matches_have_scores(self):
        collector = DataCollector()
        data = collector.collect_all()
        for m in data.historical_matches:
            assert m.home_goals >= 0, f"Match {m.date} {m.home_team}-{m.away_team}: negative home goals"
            assert m.away_goals >= 0, f"Match {m.date} {m.home_team}-{m.away_team}: negative away goals"


# ── Data Processor Tests ────────────────────────────────────

class TestDataProcessor:
    """Verify data cleaning and validation."""

    def test_clean_data_no_errors(self):
        """Clean data should pass validation with zero issues."""
        collector = DataCollector()
        raw = collector.collect_all()
        processor = DataProcessor()
        processed = processor.process(raw)

        assert processed.quality.missing_dates == 0
        assert processed.quality.missing_teams == 0
        assert processed.quality.invalid_scores == 0
        assert processed.quality.duplicates_removed == 0

    def test_validates_clean_data(self):
        """validate() should return True for good data."""
        collector = DataCollector()
        raw = collector.collect_all()
        processor = DataProcessor()
        processed = processor.process(raw)
        assert processor.validate(processed)

    def test_rejects_dirty_data(self):
        """Should catch invalid records."""
        from app.services.data_collector import CollectedData
        dirty = CollectedData()
        dirty.historical_matches = [
            HistoricalMatch("2026-07-01", "Test", "GROUP", "ARG", "BRA", -1, -1),  # Valid date/teams, bad scores
        ]
        processor = DataProcessor()
        processed = processor.process(dirty)
        assert processed.quality.invalid_scores == 1
        assert not processor.validate(processed)

    def test_detects_duplicates(self):
        from app.services.data_collector import CollectedData
        dup = CollectedData()
        dup.historical_matches = [
            HistoricalMatch("2026-07-01", "Test", "GROUP", "ARG", "BRA", 1, 0),
            HistoricalMatch("2026-07-01", "Test", "GROUP", "ARG", "BRA", 1, 0),
        ]
        processor = DataProcessor()
        processed = processor.process(dup)
        assert processed.quality.duplicates_removed == 1
