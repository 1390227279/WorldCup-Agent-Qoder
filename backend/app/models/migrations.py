"""Ordered, additive SQLite migrations that preserve existing local data."""

from collections.abc import Callable

from sqlalchemy import inspect, text

from app.models.tournament import (
    DEFAULT_TOURNAMENT_CODE,
    DEFAULT_TOURNAMENT_DATA_VERSION,
    DEFAULT_TOURNAMENT_NAME,
    DEFAULT_TOURNAMENT_NAME_CN,
    DEFAULT_TOURNAMENT_RULES_VERSION,
    DEFAULT_TOURNAMENT_STATUS,
)


EVENT_METADATA_MIGRATION_VERSION = "20260713_event_metadata_v1"
TOURNAMENT_DOMAIN_MIGRATION_VERSION = "20260714_tournament_domain_v1"

def _migrate_event_metadata(connection) -> None:
    tables = set(inspect(connection).get_table_names())
    if "events" not in tables:
        return

    columns = {column["name"] for column in inspect(connection).get_columns("events")}
    additions = {
        "source_type": "VARCHAR(30) NOT NULL DEFAULT 'MANUAL'",
        "source_url": "VARCHAR(500)",
        "external_id": "VARCHAR(200)",
        "effective_at": "DATETIME",
        "expires_at": "DATETIME",
        "updated_at": "DATETIME",
    }
    for name, definition in additions.items():
        if name not in columns:
            connection.execute(text(f"ALTER TABLE events ADD COLUMN {name} {definition}"))

    connection.execute(
        text("UPDATE events SET source_type = 'MANUAL' WHERE source_type IS NULL")
    )
    connection.execute(
        text("UPDATE events SET updated_at = created_at WHERE updated_at IS NULL")
    )
    connection.execute(
        text("CREATE INDEX IF NOT EXISTS ix_events_external_id ON events (external_id)")
    )


def _migrate_tournament_domain(connection) -> None:
    connection.execute(text(
        "CREATE TABLE IF NOT EXISTS tournaments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "code VARCHAR(50) NOT NULL UNIQUE, "
        "name VARCHAR(150) NOT NULL, "
        "name_cn VARCHAR(150) NOT NULL, "
        "year INTEGER NOT NULL, "
        "status VARCHAR(20) NOT NULL DEFAULT 'DRAFT', "
        "data_version VARCHAR(100) NOT NULL DEFAULT 'legacy-seed-v1', "
        "rules_version VARCHAR(100) NOT NULL DEFAULT 'pending-v1', "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    ))
    connection.execute(text(
        "CREATE TABLE IF NOT EXISTS tournament_teams ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE, "
        "team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE, "
        "group_name VARCHAR(2), "
        "pot INTEGER, "
        "qualification_status VARCHAR(20) NOT NULL DEFAULT 'PENDING', "
        "active BOOLEAN NOT NULL DEFAULT 1, "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT uq_tournament_teams_tournament_team "
        "UNIQUE (tournament_id, team_id))"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_tournaments_code ON tournaments (code)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_tournament_teams_tournament_id "
        "ON tournament_teams (tournament_id)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_tournament_teams_team_id "
        "ON tournament_teams (team_id)"
    ))

    connection.execute(
        text(
            "INSERT INTO tournaments "
            "(code, name, name_cn, year, status, data_version, rules_version, "
            "created_at, updated_at) "
            "SELECT :code, :name, :name_cn, :year, :status, :data_version, "
            ":rules_version, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
            "WHERE NOT EXISTS (SELECT 1 FROM tournaments WHERE code = :code)"
        ),
        {
            "code": DEFAULT_TOURNAMENT_CODE,
            "name": DEFAULT_TOURNAMENT_NAME,
            "name_cn": DEFAULT_TOURNAMENT_NAME_CN,
            "year": 2026,
            "status": DEFAULT_TOURNAMENT_STATUS,
            "data_version": DEFAULT_TOURNAMENT_DATA_VERSION,
            "rules_version": DEFAULT_TOURNAMENT_RULES_VERSION,
        },
    )

    tables = set(inspect(connection).get_table_names())
    if "teams" not in tables:
        return

    team_columns = {
        column["name"] for column in inspect(connection).get_columns("teams")
    }
    group_expression = "team.group_name" if "group_name" in team_columns else "NULL"
    pot_expression = "team.pot" if "pot" in team_columns else "NULL"
    connection.execute(text(
        "INSERT INTO tournament_teams "
        "(tournament_id, team_id, group_name, pot, qualification_status, active, "
        "created_at, updated_at) "
        f"SELECT tournament.id, team.id, {group_expression}, {pot_expression}, "
        "'LEGACY', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
        "FROM tournaments AS tournament CROSS JOIN teams AS team "
        "WHERE tournament.code = :code "
        "AND NOT EXISTS ("
        "SELECT 1 FROM tournament_teams AS existing "
        "WHERE existing.tournament_id = tournament.id "
        "AND existing.team_id = team.id)"
    ), {"code": DEFAULT_TOURNAMENT_CODE})


Migration = tuple[str, Callable]
MIGRATIONS: tuple[Migration, ...] = (
    (EVENT_METADATA_MIGRATION_VERSION, _migrate_event_metadata),
    (TOURNAMENT_DOMAIN_MIGRATION_VERSION, _migrate_tournament_domain),
)
MIGRATION_VERSIONS = tuple(version for version, _ in MIGRATIONS)


def run_migrations(connection) -> None:
    """Apply all known migrations in order and keep each migration idempotent."""
    connection.execute(text(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version VARCHAR(100) PRIMARY KEY, "
        "applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    ))

    for version, migration in MIGRATIONS:
        applied = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :version"),
            {"version": version},
        ).first()
        if applied:
            continue

        migration(connection)
        connection.execute(
            text("INSERT INTO schema_migrations (version) VALUES (:version)"),
            {"version": version},
        )
