"""Online selection of one representative tournament path per champion."""

from dataclasses import dataclass

from app.services.simulation_models import TournamentOutcome


REPRESENTATIVE_PATH_TYPE = "top_champion_highest_likelihood_sample"


class RepresentativePathError(ValueError):
    """Raised when a representative path candidate is unavailable."""


@dataclass(frozen=True, slots=True)
class RepresentativePathCandidate:
    champion_team_id: int
    iteration_index: int
    iteration_seed: int
    log_likelihood: float


class RepresentativePathSelector:
    """Keep only the highest-likelihood observed sample for each champion."""

    def __init__(self) -> None:
        self._best_by_champion: dict[int, RepresentativePathCandidate] = {}

    def observe(
        self,
        outcome: TournamentOutcome,
        *,
        iteration_index: int,
        iteration_seed: int,
    ) -> None:
        candidate = RepresentativePathCandidate(
            champion_team_id=outcome.champion_team_id,
            iteration_index=iteration_index,
            iteration_seed=iteration_seed,
            log_likelihood=outcome.log_likelihood,
        )
        current = self._best_by_champion.get(outcome.champion_team_id)
        if current is None or self._is_better(candidate, current):
            self._best_by_champion[outcome.champion_team_id] = candidate

    @staticmethod
    def _is_better(
        candidate: RepresentativePathCandidate,
        current: RepresentativePathCandidate,
    ) -> bool:
        if candidate.log_likelihood != current.log_likelihood:
            return candidate.log_likelihood > current.log_likelihood
        return candidate.iteration_seed < current.iteration_seed

    def for_champion(self, champion_team_id: int) -> RepresentativePathCandidate:
        candidate = self._best_by_champion.get(champion_team_id)
        if candidate is None:
            raise RepresentativePathError(
                f"No representative sample found for champion {champion_team_id}"
            )
        return candidate

    @property
    def candidate_count(self) -> int:
        return len(self._best_by_champion)
