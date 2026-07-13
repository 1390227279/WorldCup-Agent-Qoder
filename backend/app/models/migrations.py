"""Small versioned SQLite migrations for preserving local demo data."""

from sqlalchemy import inspect, text


MIGRATION_VERSION = "20260713_event_metadata_v1"


def run_migrations(connection) -> None:
    connection.execute(text(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version VARCHAR(100) PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    ))
    applied = connection.execute(
        text("SELECT 1 FROM schema_migrations WHERE version = :version"),
        {"version": MIGRATION_VERSION},
    ).first()
    if applied:
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_events_external_id ON events (external_id)"
        ))
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
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_events_external_id ON events (external_id)"
    ))
    connection.execute(
        text("INSERT INTO schema_migrations (version) VALUES (:version)"),
        {"version": MIGRATION_VERSION},
    )
