"""API test fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from pydantic_ai.models.test import TestModel

from typed_code.api.app import create_app
from typed_code.config.credentials import Credentials, ProviderAvailability
from typed_code.config.settings import Settings
from typed_code.persistence.db import open_database
from typed_code.persistence.repository import SessionRepository
from typed_code.providers.catalog import ModelCatalog
from typed_code.runtime.adapter import AgentRuntime
from typed_code.service.app_state import AppState
from typed_code.service.event_bus import EventBus
from typed_code.service.publishing import PublishingRepository
from typed_code.service.session_manager import SessionManager


@pytest.fixture
def token() -> str:
    return "test-server-token"


@pytest_asyncio.fixture
async def api_env(
    tmp_path: Path,
    token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AppState, Path, str]]:
    ws = tmp_path / "workspace"
    ws.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config_dir = tmp_path / "config" / "typed-code"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        f'[data]\ndir = "{data_dir}"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    settings = Settings(
        data_dir=data_dir,
        host="127.0.0.1",
        port=8741,
        event_retention_count=50,
        bash_executable="/bin/bash",
    )
    credentials = Credentials(
        server_token=SecretStr(token),
        deepseek_api_key=SecretStr("ds"),
        cliproxy_api_key=SecretStr("cp"),
        server_token_present=True,
        deepseek_availability=ProviderAvailability.AVAILABLE,
        cliproxy_availability=ProviderAvailability.AVAILABLE,
    )

    database = await open_database(data_dir / "typed-code.db")
    event_bus = EventBus()
    base_repo = SessionRepository(database, event_retention_count=50)
    repository: SessionRepository = PublishingRepository(base_repo, event_bus.publish)
    catalog = ModelCatalog(settings=settings, credentials=credentials)
    catalog.seed_cliproxy_models({settings.default_model, "gpt-5.6-sol"})
    runtime = AgentRuntime(
        repository=repository,
        catalog=catalog,
        settings=settings,
        model_override=TestModel(custom_output_text="hello from test"),
        enable_workspace_tools=False,
        auto_approve_mutations=True,
    )
    manager = SessionManager(
        repository=repository,
        runtime=runtime,
        event_bus=event_bus,
    )
    await manager.recover()

    state = AppState(
        settings=settings,
        credentials=credentials,
        database=database,
        repository=repository,
        catalog=catalog,
        runtime=runtime,
        manager=manager,
        event_bus=event_bus,
        bash_ready=True,
        bash_executable="/bin/bash",
    )
    try:
        yield state, ws, token
    finally:
        # Drain background turn tasks before closing the DB
        import asyncio

        pending = [t for t in manager._tasks.values() if not t.done()]
        if pending:
            await asyncio.wait(pending, timeout=5.0)
        await database.close()


@pytest_asyncio.fixture
async def client(api_env: tuple[AppState, Path, str]) -> AsyncIterator[AsyncClient]:
    state, _ws, _token = api_env
    app = create_app(state=state)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
