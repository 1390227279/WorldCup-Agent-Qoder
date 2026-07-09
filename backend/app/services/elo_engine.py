"""
ELO Rating Engine — calculates and updates team ELO ratings.

The ELO system is a method for calculating the relative skill levels of teams.
After each match, ratings are updated based on:
- The expected outcome (higher-rated team expected to win)
- The actual outcome (win/draw/loss)
- The K-factor (how much a single match can change ratings)
- Goal difference multiplier (more decisive wins → bigger rating changes)

Reference: World Football ELO Ratings methodology (eloratings.net)
"""

import math
from dataclasses import dataclass
from typing import Optional


# ── ELO Constants ──────────────────────────────────────────

DEFAULT_ELO = 1500.0          # Starting rating for new teams
HOME_ADVANTAGE = 100.0        # Points added to home team's rating
K_FACTOR_BASE = 40.0          # Base K-factor for World Cup matches
K_FACTOR_KNOCKOUT = 60.0      # Higher K for knockout stage (more impactful)
SCALE_FACTOR = 400.0          # Standard ELO scale factor


@dataclass
class MatchResult:
    """Input data for a single match that affects ELO."""
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    is_neutral_venue: bool = True   # World Cup matches are mostly neutral
    is_knockout: bool = False
    weight: float = 1.0             # Competition weight (World Cup = 1.0)


@dataclass
class EloUpdate:
    """Result of an ELO rating update."""
    team: str
    old_rating: float
    new_rating: float
    change: float


# ── Core ELO Functions ──────────────────────────────────────

def expected_score(rating_a: float, rating_b: float) -> float:
    """
    Calculate the expected score for team A against team B.

    Formula: E_A = 1 / (1 + 10^((R_B - R_A) / 400))

    Returns a value between 0 and 1:
    - 0.5 = evenly matched
    - >0.5 = team A favored
    - <0.5 = team B favored

    Example:
        Brazil (2100) vs China (1350)
        E_Brazil = 1 / (1 + 10^((1350-2100)/400))
                 = 1 / (1 + 10^(-1.875))
                 = 1 / (1 + 0.0133)
                 ≈ 0.987  (Brazil has ~98.7% chance to win)
    """
    return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / SCALE_FACTOR))


def goal_difference_multiplier(goal_diff: int) -> float:
    """
    Bigger wins produce bigger ELO changes.

    Formula: M = 1 if margin <= 1
             M = 1.5 if margin == 2
             M = (11 + margin) / 8 if margin >= 3

    Examples:
        margin=1 → M=1.0   (close game, minimal adjustment)
        margin=2 → M=1.5
        margin=3 → M=1.75
        margin=5 → M=2.0   (blowout, significant adjustment)
    """
    margin = abs(goal_diff)
    if margin <= 1:
        return 1.0
    if margin == 2:
        return 1.5
    return (11.0 + margin) / 8.0


def calculate_elo_update(
    rating_home: float,
    rating_away: float,
    home_goals: int,
    away_goals: int,
    is_neutral: bool = True,
    is_knockout: bool = False,
    weight: float = 1.0,
) -> tuple[EloUpdate, EloUpdate]:
    """
    Calculate ELO changes after a match.

    Returns the updates for both home and away teams.

    How it works step by step:

    1. Adjust for home advantage
       effective_home = rating_home + (0 if neutral else HOME_ADVANTAGE)

    2. Calculate expected score
       E_home = expected_score(effective_home, rating_away)

    3. Determine actual outcome
       home_goals > away_goals → S_home = 1.0 (win)
       home_goals == away_goals → S_home = 0.5 (draw)
       home_goals < away_goals → S_home = 0.0 (loss)

    4. Calculate K-factor
       K = K_FACTOR_KNOCKOUT if knockout else K_FACTOR_BASE
       K *= weight (competition importance)
       K *= goal_difference_multiplier(goal_diff)

    5. Apply the update
       new_rating = old_rating + K * (actual_outcome - expected_outcome)
    """
    # Step 1: Home advantage
    effective_home = rating_home if is_neutral else rating_home + HOME_ADVANTAGE

    # Step 2: Expected score
    expected_home = expected_score(effective_home, rating_away)
    expected_away = 1.0 - expected_home

    # Step 3: Actual outcome
    if home_goals > away_goals:
        actual_home, actual_away = 1.0, 0.0
    elif home_goals == away_goals:
        actual_home, actual_away = 0.5, 0.5
    else:
        actual_home, actual_away = 0.0, 1.0

    # Step 4: K-factor
    k = K_FACTOR_KNOCKOUT if is_knockout else K_FACTOR_BASE
    k *= weight
    k *= goal_difference_multiplier(home_goals - away_goals)

    # Step 5: Apply update
    change_home = k * (actual_home - expected_home)
    change_away = k * (actual_away - expected_away)

    return (
        EloUpdate(
            team="home",
            old_rating=rating_home,
            new_rating=rating_home + change_home,
            change=change_home,
        ),
        EloUpdate(
            team="away",
            old_rating=rating_away,
            new_rating=rating_away + change_away,
            change=change_away,
        ),
    )


# ── Batch Processing ────────────────────────────────────────

def process_match_history(
    initial_ratings: dict[str, float],
    matches: list[MatchResult],
) -> dict[str, float]:
    """
    Process a sequence of matches and return final ELO ratings.

    This is the function you call to:
    - Calculate current ELO ratings from scratch given historical matches
    - Simulate how ratings would change after a series of tournament matches

    Args:
        initial_ratings: {team_name: starting_elo}
        matches: ordered list of match results (chronological)

    Returns:
        {team_name: final_elo} after processing all matches
    """
    ratings = dict(initial_ratings)

    for match in matches:
        # Get current ratings (use default for unknown teams)
        home_elo = ratings.get(match.home_team, DEFAULT_ELO)
        away_elo = ratings.get(match.away_team, DEFAULT_ELO)

        update_home, update_away = calculate_elo_update(
            rating_home=home_elo,
            rating_away=away_elo,
            home_goals=match.home_goals,
            away_goals=match.away_goals,
            is_neutral=match.is_neutral_venue,
            is_knockout=match.is_knockout,
            weight=match.weight,
        )

        ratings[match.home_team] = update_home.new_rating
        ratings[match.away_team] = update_away.new_rating

    return ratings


# ── Utility Functions ───────────────────────────────────────

def normalize_elo(elo: float, min_elo: float = 1000, max_elo: float = 2200) -> float:
    """
    Normalize an ELO rating to a 0-100 scale.

    This is used by the Agent's tools to present ELO in an
    easy-to-understand format alongside other metrics.
    """
    clamped = max(min_elo, min(max_elo, elo))
    return ((clamped - min_elo) / (max_elo - min_elo)) * 100


def elo_to_win_probability(elo_a: float, elo_b: float) -> float:
    """
    Convert ELO rating difference to win probability for team A.

    Convenience wrapper around expected_score().
    """
    return expected_score(elo_a, elo_b)


def rating_gap(elo_a: float, elo_b: float) -> float:
    """Absolute ELO gap between two teams."""
    return abs(elo_a - elo_b)
