"""Schema migration and pragma checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from typed_code.persistence import open_database
from typed_code.persistence.migrations import apply_migrations


@pytest.mark.asyncio
async def test_fresh_database_applies_initial_migration(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    db = await open_database(path)
    try:
        cursor = await db.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        versions = [int(r[0]) for r in await cursor.fetchall()]
        assert versions == [1, 2]

        cursor = await db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {r[0] for r in await cursor.fetchall()}
        assert {
            "sessions",
            "runs",
            "model_messages",
            "transcript_items",
            "events",
            "approvals",
            "history_archives",
            "schema_migrations",
        }.issubset(tables)

        cursor = await db.connection.execute("PRAGMA foreign_keys")
        fk_row = await cursor.fetchone()
        assert fk_row is not None and fk_row[0] == 1

        cursor = await db.connection.execute("PRAGMA journal_mode")
        mode_row = await cursor.fetchone()
        assert mode_row is not None
        assert str(mode_row[0]).lower() == "wal"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_migrations_are_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    db = await open_database(path)
    try:
        await apply_migrations(db.connection)
        cursor = await db.connection.execute("SELECT COUNT(*) FROM schema_migrations")
        count_row = await cursor.fetchone()
        assert count_row is not None and count_row[0] == 2
    finally:
        await db.close()
