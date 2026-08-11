"""Persistence test fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from typed_code.persistence import Database, SessionRepository, open_database
from typed_code.protocol.common import ProviderName


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    path = tmp_path / "typed-code.db"
    database = await open_database(path)
    try:
        yield database
    finally:
        await database.close()


@pytest_asyncio.fixture
async def repo(db: Database) -> SessionRepository:
    return SessionRepository(db, event_retention_count=5)


@pytest_asyncio.fixture
async def seeded_session(repo: SessionRepository) -> str:
    result = await repo.create_session(
        workspace_path="/tmp/workspace",
        provider=ProviderName.CLIPROXY,
        model="gpt-5.6-sol",
    )
    return result.snapshot.session_id
