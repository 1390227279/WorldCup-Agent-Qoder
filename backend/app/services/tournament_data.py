"""Load, validate, and synchronize versioned tournament participant data."""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.tournament import Tournament, TournamentTeam


DEFAULT_TOURNAMENT_DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "resources"
    / "tournaments"
    / "world_cup_2026.json"
)
EXPECTED_GROUPS = tuple("ABCDEFGHIJKL")
EXPECTED_PARTICIPANT_COUNT = 48


class TournamentDataError(ValueError):
    """Raised when a tournament dataset is invalid or cannot be synchronized."""


@dataclass(frozen=True, slots=True)
class TournamentMetadata:
    code: str
    name: str
    name_cn: str
    year: int
    status: str
    data_version: str
    rules_version: str
    dataset_kind: str
    is_official: bool
    source_name: str
    source_url: str
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class TournamentParticipantData:
    fifa_code: str
    name: str
    name_cn: str
    group_name: str
    pot: int
    qualification_status: str
    source_url: str


@dataclass(frozen=True, slots=True)
class TeamDefaultData:
    fifa_code: str
    confederation: str
    fifa_ranking: int | None
    elo_rating: float
    stats: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TournamentDataset:
    schema_version: int
    tournament: TournamentMetadata
    participants: tuple[TournamentParticipantData, ...]
    team_defaults: tuple[TeamDefaultData, ...]


@dataclass(frozen=True, slots=True)
class TournamentSyncResult:
    tournament_id: int
    active_participants: int
    teams_created: int
    participants_created: int
    participants_updated: int
    participants_deactivated: int


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TournamentDataError(f"{field} must be an object")
    return value


def _require_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise TournamentDataError(f"{field} must be an array")
    return value


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TournamentDataError(f"{field} must be a non-empty string")
    return value.strip()


def load_tournament_dataset(
    path: str | Path = DEFAULT_TOURNAMENT_DATA_PATH,
) -> TournamentDataset:
    """Read and validate a versioned tournament dataset."""
    source_path = Path(path)
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TournamentDataError(
            f"Unable to load tournament dataset {source_path}: {exc}"
        ) from exc

    root = _require_mapping(raw, "root")
    metadata_raw = _require_mapping(root.get("tournament"), "tournament")
    metadata = TournamentMetadata(
        code=_require_string(metadata_raw.get("code"), "tournament.code"),
        name=_require_string(metadata_raw.get("name"), "tournament.name"),
        name_cn=_require_string(metadata_raw.get("name_cn"), "tournament.name_cn"),
        year=int(metadata_raw.get("year")),
        status=_require_string(metadata_raw.get("status"), "tournament.status").upper(),
        data_version=_require_string(
            metadata_raw.get("data_version"), "tournament.data_version"
        ),
        rules_version=_require_string(
            metadata_raw.get("rules_version"), "tournament.rules_version"
        ),
        dataset_kind=_require_string(
            metadata_raw.get("dataset_kind"), "tournament.dataset_kind"
        ).upper(),
        is_official=bool(metadata_raw.get("is_official")),
        source_name=_require_string(
            metadata_raw.get("source_name"), "tournament.source_name"
        ),
        source_url=_require_string(
            metadata_raw.get("source_url"), "tournament.source_url"
        ),
        notes=metadata_raw.get("notes"),
    )

    participants = []
    for index, item in enumerate(_require_list(root.get("participants"), "participants")):
        entry = _require_mapping(item, f"participants[{index}]")
        participants.append(TournamentParticipantData(
            fifa_code=_require_string(
                entry.get("fifa_code"), f"participants[{index}].fifa_code"
            ).upper(),
            name=_require_string(entry.get("name"), f"participants[{index}].name"),
            name_cn=_require_string(
                entry.get("name_cn"), f"participants[{index}].name_cn"
            ),
            group_name=_require_string(
                entry.get("group_name"), f"participants[{index}].group_name"
            ).upper(),
            pot=int(entry.get("pot")),
            qualification_status=_require_string(
                entry.get("qualification_status"),
                f"participants[{index}].qualification_status",
            ).upper(),
            source_url=_require_string(
                entry.get("source_url"), f"participants[{index}].source_url"
            ),
        ))

    team_defaults = []
    for index, item in enumerate(_require_list(root.get("team_defaults", []), "team_defaults")):
        entry = _require_mapping(item, f"team_defaults[{index}]")
        rating = entry.get("fifa_ranking")
        team_defaults.append(TeamDefaultData(
            fifa_code=_require_string(
                entry.get("fifa_code"), f"team_defaults[{index}].fifa_code"
            ).upper(),
            confederation=_require_string(
                entry.get("confederation"), f"team_defaults[{index}].confederation"
            ).upper(),
            fifa_ranking=int(rating) if rating is not None else None,
            elo_rating=float(entry.get("elo_rating", 1500.0)),
            stats=_require_mapping(entry.get("stats", {}), f"team_defaults[{index}].stats"),
        ))

    dataset = TournamentDataset(
        schema_version=int(root.get("schema_version", 0)),
        tournament=metadata,
        participants=tuple(participants),
        team_defaults=tuple(team_defaults),
    )
    validate_tournament_dataset(dataset)
    return dataset


def validate_tournament_dataset(dataset: TournamentDataset) -> None:
    """Validate participant count, groups, pots, codes, and source semantics."""
    if dataset.schema_version != 1:
        raise TournamentDataError(
            f"Unsupported tournament schema version: {dataset.schema_version}"
        )
    if len(dataset.participants) != EXPECTED_PARTICIPANT_COUNT:
        raise TournamentDataError(
            f"Expected {EXPECTED_PARTICIPANT_COUNT} participants, "
            f"got {len(dataset.participants)}"
        )

    codes = [participant.fifa_code for participant in dataset.participants]
    if any(len(code) != 3 or not code.isalpha() for code in codes):
        raise TournamentDataError("Every FIFA code must contain three letters")
    if len(set(codes)) != len(codes):
        raise TournamentDataError("Tournament participant FIFA codes must be unique")

    group_counts = Counter(
        participant.group_name for participant in dataset.participants
    )
    expected_group_counts = {group: 4 for group in EXPECTED_GROUPS}
    if dict(group_counts) != expected_group_counts:
        raise TournamentDataError(
            f"Expected groups A-L with four teams each, got {dict(group_counts)}"
        )

    for group in EXPECTED_GROUPS:
        pots = {
            participant.pot
            for participant in dataset.participants
            if participant.group_name == group
        }
        if pots != {1, 2, 3, 4}:
            raise TournamentDataError(
                f"Group {group} must contain exactly one team from each pot"
            )

    fallback_codes = [team.fifa_code for team in dataset.team_defaults]
    if len(set(fallback_codes)) != len(fallback_codes):
        raise TournamentDataError("Team default FIFA codes must be unique")
    if not set(fallback_codes) <= set(codes):
        raise TournamentDataError("Team defaults must belong to tournament participants")

    metadata = dataset.tournament
    if metadata.is_official and metadata.dataset_kind != "OFFICIAL":
        raise TournamentDataError("Official datasets must use dataset_kind=OFFICIAL")
    if not metadata.is_official and metadata.status == "OFFICIAL":
        raise TournamentDataError("Non-official datasets cannot use status=OFFICIAL")


async def sync_tournament_dataset(
    session: AsyncSession,
    dataset: TournamentDataset | None = None,
) -> TournamentSyncResult:
    """Synchronize one dataset without deleting global teams or historical entries."""
    dataset = dataset or load_tournament_dataset()
    metadata = dataset.tournament

    tournament_result = await session.execute(
        select(Tournament).where(Tournament.code == metadata.code)
    )
    tournament = tournament_result.scalar_one_or_none()
    if tournament is None:
        tournament = Tournament(code=metadata.code)
        session.add(tournament)

    tournament.name = metadata.name
    tournament.name_cn = metadata.name_cn
    tournament.year = metadata.year
    tournament.status = metadata.status
    tournament.data_version = metadata.data_version
    tournament.rules_version = metadata.rules_version
    await session.flush()

    participant_codes = {entry.fifa_code for entry in dataset.participants}
    teams_result = await session.execute(
        select(Team).where(Team.fifa_code.in_(participant_codes))
    )
    teams_by_code = {team.fifa_code: team for team in teams_result.scalars().all()}
    defaults_by_code = {team.fifa_code: team for team in dataset.team_defaults}

    teams_created = 0
    for participant in dataset.participants:
        if participant.fifa_code in teams_by_code:
            continue
        defaults = defaults_by_code.get(participant.fifa_code)
        if defaults is None:
            raise TournamentDataError(
                f"Team {participant.fifa_code} is missing from the global team table "
                "and has no team_defaults entry"
            )
        team = Team(
            name=participant.name,
            name_cn=participant.name_cn,
            fifa_code=participant.fifa_code,
            confederation=defaults.confederation,
            fifa_ranking=defaults.fifa_ranking,
            elo_rating=defaults.elo_rating,
            group_name=participant.group_name,
            pot=participant.pot,
            stats=defaults.stats,
        )
        session.add(team)
        teams_by_code[participant.fifa_code] = team
        teams_created += 1
    await session.flush()

    entries_result = await session.execute(
        select(TournamentTeam).where(TournamentTeam.tournament_id == tournament.id)
    )
    entries = entries_result.scalars().all()
    entries_by_team_id = {entry.team_id: entry for entry in entries}

    participants_created = 0
    participants_updated = 0
    active_team_ids = set()
    for participant in dataset.participants:
        team = teams_by_code[participant.fifa_code]
        active_team_ids.add(team.id)
        entry = entries_by_team_id.get(team.id)
        if entry is None:
            entry = TournamentTeam(tournament_id=tournament.id, team_id=team.id)
            session.add(entry)
            participants_created += 1
        else:
            participants_updated += 1
        entry.group_name = participant.group_name
        entry.pot = participant.pot
        entry.qualification_status = participant.qualification_status
        entry.active = True

    participants_deactivated = 0
    for entry in entries:
        if entry.team_id not in active_team_ids and entry.active:
            entry.active = False
            participants_deactivated += 1

    await session.flush()
    return TournamentSyncResult(
        tournament_id=tournament.id,
        active_participants=len(active_team_ids),
        teams_created=teams_created,
        participants_created=participants_created,
        participants_updated=participants_updated,
        participants_deactivated=participants_deactivated,
    )
