from sqlalchemy import create_engine, inspect, text

from app.models.migrations import MIGRATION_VERSION, run_migrations


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
        assert {"source_type", "source_url", "external_id", "effective_at", "expires_at", "updated_at"} <= columns
        row = connection.execute(text("SELECT title, source_type FROM events WHERE id = 1")).one()
        assert row == ("旧事件", "MANUAL")
        version = connection.execute(text("SELECT version FROM schema_migrations")).scalar_one()
        assert version == MIGRATION_VERSION
