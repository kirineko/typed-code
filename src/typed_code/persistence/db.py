"""aiosqlite database open helpers with WAL and foreign keys."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import TracebackType

import aiosqlite

from typed_code.persistence.migrations import apply_migrations


class Database:
    """Thin wrapper around an aiosqlite connection used by repositories."""

    def __init__(self, conn: aiosqlite.Connection, path: Path) -> None:
        self._conn = conn
        self.path = path
        self._write_lock = asyncio.Lock()

    @property
    def connection(self) -> aiosqlite.Connection:
        return self._conn

    @asynccontextmanager
    async def write_transaction(self) -> AsyncIterator[None]:
        """Serialize one complete SQLite write transaction on the shared connection."""
        async with self._write_lock:
            await self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield
            except BaseException:
                await self._conn.rollback()
                raise
            else:
                await self._conn.commit()

    async def close(self) -> None:
        await self._conn.close()

    async def __aenter__(self) -> Database:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()


async def open_database(path: Path, *, migrate: bool = True) -> Database:
    """Open (or create) a SQLite database with WAL + foreign keys enabled."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA foreign_keys=ON;")
    await conn.execute("PRAGMA busy_timeout=5000;")
    if migrate:
        await apply_migrations(conn)
    return Database(conn, path)
