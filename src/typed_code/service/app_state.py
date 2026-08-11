"""Process-wide application state for the HTTP service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from typed_code.config.credentials import Credentials, load_credentials
from typed_code.config.errors import ConfigurationError
from typed_code.config.settings import Settings, load_settings
from typed_code.persistence.db import Database, open_database
from typed_code.persistence.repository import SessionRepository
from typed_code.providers.catalog import ModelCatalog
from typed_code.runtime.adapter import AgentRuntime
from typed_code.service.event_bus import EventBus
from typed_code.service.publishing import PublishingRepository
from typed_code.service.session_manager import SessionManager
from typed_code.workspace.bash import detect_bash
from typed_code.workspace.errors import BashUnavailableError


@dataclass
class AppState:
    settings: Settings
    credentials: Credentials
    database: Database
    repository: SessionRepository
    catalog: ModelCatalog
    runtime: AgentRuntime
    manager: SessionManager
    event_bus: EventBus
    bash_ready: bool
    bash_executable: str | None

    async def aclose(self) -> None:
        await self.database.close()

    async def reload_configuration(self) -> dict[str, str]:
        """Re-read XDG settings/credentials; keep previous on failure.

        Returns secret-free provider availability map.
        """
        try:
            new_settings = load_settings()
            new_credentials = load_credentials()
        except ConfigurationError:
            raise

        self.settings = new_settings
        self.credentials = new_credentials
        self.catalog.settings = new_settings
        self.catalog.credentials = new_credentials
        self.runtime.reload_settings(new_settings)
        try:
            await self.catalog.refresh_cliproxy()
        except Exception:
            pass

        try:
            bash_path = detect_bash(new_settings.bash_executable)
            self.bash_ready = True
            self.bash_executable = str(bash_path)
        except BashUnavailableError:
            self.bash_ready = False
            self.bash_executable = new_settings.bash_executable

        return {
            "deepseek": new_credentials.deepseek_availability.value,
            "cliproxy": new_credentials.cliproxy_availability.value,
        }


async def build_app_state(
    *,
    settings: Settings | None = None,
    credentials: Credentials | None = None,
    database_path: Path | None = None,
    runtime: AgentRuntime | None = None,
    require_server_token: bool = True,
) -> AppState:
    settings = settings or load_settings()
    credentials = credentials or load_credentials()

    if require_server_token and not credentials.can_start_authenticated_api():
        raise ConfigurationError(
            "missing_server_token",
            "typed-code server token is required to start authenticated API routes",
        )

    db_path = database_path or (settings.data_dir / "typed-code.db")
    database = await open_database(db_path)
    event_bus = EventBus()
    base_repo = SessionRepository(
        database, event_retention_count=settings.event_retention_count
    )
    repository: SessionRepository = PublishingRepository(base_repo, event_bus.publish)

    catalog = ModelCatalog(settings=settings, credentials=credentials)
    try:
        await catalog.refresh_cliproxy()
    except Exception:
        pass

    agent_runtime = runtime or AgentRuntime(
        repository=repository,
        catalog=catalog,
        settings=settings,
        enable_workspace_tools=True,
    )
    agent_runtime.repository = repository

    manager = SessionManager(
        repository=repository,
        runtime=agent_runtime,
        event_bus=event_bus,
    )
    await manager.recover()

    bash_ready = False
    bash_exec: str | None = None
    try:
        bash_path = detect_bash(settings.bash_executable)
        bash_ready = True
        bash_exec = str(bash_path)
    except BashUnavailableError:
        bash_ready = False
        bash_exec = settings.bash_executable

    return AppState(
        settings=settings,
        credentials=credentials,
        database=database,
        repository=repository,
        catalog=catalog,
        runtime=agent_runtime,
        manager=manager,
        event_bus=event_bus,
        bash_ready=bash_ready,
        bash_executable=bash_exec,
    )
