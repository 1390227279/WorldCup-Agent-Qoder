from app.services.representative_path import RepresentativePathSelector
from app.services.simulation_models import TournamentOutcome


def _outcome(champion_team_id: int, log_likelihood: float) -> TournamentOutcome:
    return TournamentOutcome(
        champion_team_id=champion_team_id,
        champion_name=f"Team {champion_team_id}",
        reached_team_ids={"CHAMPION": (champion_team_id,)},
        log_likelihood=log_likelihood,
    )


def test_selector_keeps_only_best_candidate_per_champion():
    selector = RepresentativePathSelector()
    selector.observe(_outcome(1, -120.0), iteration_index=0, iteration_seed=100)
    selector.observe(_outcome(1, -90.0), iteration_index=1, iteration_seed=200)
    selector.observe(_outcome(2, -80.0), iteration_index=2, iteration_seed=300)

    assert selector.candidate_count == 2
    assert selector.for_champion(1).iteration_seed == 200
    assert selector.for_champion(1).log_likelihood == -90.0
    assert selector.for_champion(2).iteration_seed == 300


def test_selector_uses_lower_seed_as_stable_tiebreaker():
    selector = RepresentativePathSelector()
    selector.observe(_outcome(1, -50.0), iteration_index=0, iteration_seed=300)
    selector.observe(_outcome(1, -50.0), iteration_index=1, iteration_seed=100)

    assert selector.for_champion(1).iteration_seed == 100
