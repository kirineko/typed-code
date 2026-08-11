"""Schema migration runner and SQL assets."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import aiosqlite

from typed_code.domain.clock import isoformat, utc_now

# Version numbers match filename prefixes in this package.
MIGRATIONS: list[tuple[int, str]] = [
    (1, "001_initial.sql"),
    (2, "002_context_usage_checkpoint.sql"),
]


async def apply_migrations(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    await conn.commit()

    cursor = await conn.execute("SELECT version FROM schema_migrations ORDER BY version")
    applied = {int(row[0]) for row in await cursor.fetchall()}

    package = "typed_code.persistence.migrations"
    for version, filename in MIGRATIONS:
        if version in applied:
            continue
        sql = _load_sql(package, filename)
        await _executescript_skip_migrations_create(conn, sql)
        await conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, isoformat(utc_now())),
        )
        await conn.commit()


def _load_sql(package: str, filename: str) -> str:
    try:
        ref = resources.files(package).joinpath(filename)
        return ref.read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError, ModuleNotFoundError, AttributeError):
        here = Path(__file__).resolve().parent / filename
        return here.read_text(encoding="utf-8")


async def _executescript_skip_migrations_create(
    conn: aiosqlite.Connection, sql: str
) -> None:
    """Apply migration SQL, ignoring the schema_migrations DDL if already created."""
    cleaned_lines: list[str] = []
    skipping = False
    for line in sql.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("create table schema_migrations"):
            skipping = True
            continue
        if skipping:
            if stripped.startswith(");") or stripped == ");":
                skipping = False
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    await conn.executescript(cleaned)
