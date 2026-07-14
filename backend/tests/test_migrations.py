from sqlalchemy import create_engine, inspect, text

from app.models import Base
from app.models.migrations import MIGRATION_VERSIONS, run_migrations


def _applied_versions(connection) -> set[str]:
    return set(connection.execute(text("SELECT version FROM schema_migrations")).scalars())


def test_event_metadata_migration_preserves_existing_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE events ("
            "id INTEGER PRIMARY KEY, team_id INTEGER NOT NULL, type VARCHAR(20) NOT NULL, "
            "title VARCHAR(200) NOT NULL, description VARCHAR(1000), severity VARCHAR(10) NOT NULL, "
            "impact JSON, source VARCHAR(200), active BOOLEAN, created_at DATETIME)"
        ))
        connection.execute(text(
            "INSERT INTO events (id, team_id, type, title, severity, active) "
            "VALUES (1, 1, 'INJURY', '旧事件', 'MINOR', 1)"
        ))

        run_migrations(connection)
        run_migrations(connection)

        columns = {column["name"] for column in inspect(connection).get_columns("events")}
        assert {
            "source_type", "source_url", "external_id",
            "effective_at", "expires_at", "updated_at",
        } <= columns
        row = connection.execute(
            text("SELECT title, source_type FROM events WHERE id = 1")
        ).one()
        assert row == ("旧事件", "MANUAL")
        assert _applied_versions(connection) == set(MIGRATION_VERSIONS)


def test_tournament_migration_backfills_legacy_teams_idempotently(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-teams.db'}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE teams ("
            "id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, "
            "group_name VARCHAR(2), pot INTEGER)"
        ))
        connection.execute(text(
            "INSERT INTO teams (id, name, group_name, pot) VALUES "
            "(1, 'Argentina', 'C', 1), (2, 'Brazil', 'D', 1)"
        ))

        run_migrations(connection)
        run_migrations(connection)

        tables = set(inspect(connection).get_table_names())
        assert {"tournaments", "tournament_teams"} <= tables
        tournament = connection.execute(text(
            "SELECT code, status, data_version, rules_version FROM tournaments"
        )).one()
        assert tournament == (
            "world-cup-2026", "DRAFT", "legacy-seed-v1", "pending-v1"
        )
        participants = connection.execute(text(
            "SELECT team_id, group_name, pot, qualification_status, active "
            "FROM tournament_teams ORDER BY team_id"
        )).all()
        assert participants == [
            (1, "C", 1, "LEGACY", 1),
            (2, "D", 1, "LEGACY", 1),
        ]
        team_columns = {
            column["name"] for column in inspect(connection).get_columns("teams")
        }
        assert {"group_name", "pot"} <= team_columns
        assert _applied_versions(connection) == set(MIGRATION_VERSIONS)


def test_tournament_migration_supports_orm_tables_without_server_time_defaults(
    tmp_path,
):
    engine = create_engine(f"sqlite:///{tmp_path / 'orm-created.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO teams "
            "(id, name, name_cn, fifa_code, confederation, elo_rating) "
            "VALUES (1, 'Argentina', '阿根廷', 'ARG', 'CONMEBOL', 2100)"
        ))

        run_migrations(connection)

        tournament = connection.execute(text(
            "SELECT created_at, updated_at FROM tournaments "
            "WHERE code = 'world-cup-2026'"
        )).one()
        participant = connection.execute(text(
            "SELECT created_at, updated_at FROM tournament_teams "
            "WHERE team_id = 1"
        )).one()

        assert all(value is not None for value in tournament)
        assert all(value is not None for value in participant)
        assert _applied_versions(connection) == set(MIGRATION_VERSIONS)


def test_new_database_does_not_create_legacy_team_tournament_columns():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        columns = {
            column["name"] for column in inspect(connection).get_columns("teams")
        }
    assert "group_name" not in columns
    assert "pot" not in columns
