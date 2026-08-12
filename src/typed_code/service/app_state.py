"""Process-wide application state for the HTTP service."""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from typed_code import __version__
from typed_code.config.credentials import Credentials, load_credentials
from typed_code.config.errors import ConfigurationError
from typed_code.config.settings import Settings, load_settings
from typed_code.domain.clock import isoformat, utc_now
from typed_code.domain.errors import DomainConflict
from typed_code.persistence.db import Database, open_database
from typed_code.persistence.repository import SessionRepository
from typed_code.protocol.common import PROTOCOL_VERSION, SessionPhase
from typed_code.providers.catalog import ModelCatalog
from typed_code.runtime.adapter import AgentRuntime
from typed_code.service.event_bus import EventBus
from typed_code.service.idle_shutdown import IdleShutdownMonitor
from typed_code.service.publishing import PublishingRepository
from typed_code.service.runtime_identity import ServiceOwner, canonical_data_dir
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
    service_owner: ServiceOwner | None = None
    process_instance_id: str = field(default_factory=lambda: uuid4().hex)
    process_started_at: str = field(default_factory=lambda: isoformat(utc_now()))
    shutdown_requested: asyncio.Event = field(default_factory=asyncio.Event)
    idle_monitor: IdleShutdownMonitor = field(default_factory=IdleShutdownMonitor)
    _idle_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.idle_monitor.configure(self.settings.idle_timeout_seconds)

    def start_background_tasks(self) -> None:
        if self._idle_task is None or self._idle_task.done():
            self._idle_task = asyncio.create_task(self._watch_for_idle_shutdown())

    def note_authenticated_activity(self) -> None:
        self.idle_monitor.note_activity()

    async def stop_background_tasks(self) -> None:
        if self._idle_task is None:
            return
        self._idle_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._idle_task
        self._idle_task = None

    async def _watch_for_idle_shutdown(self) -> None:
        await self.idle_monitor.wait_for_shutdown(self.active_work_summary)
        self.shutdown_requested.set()

    async def aclose(self) -> None:
        await self.stop_background_tasks()
        try:
            await self.database.close()
        finally:
            if self.service_owner is not None:
                self.service_owner.close()

    async def reload_configuration(self) -> dict[str, str]:
        """Re-read XDG settings/credentials; keep previous on failure.

        Returns secret-free provider availability map.
        """
        try:
            new_settings = load_settings()
            new_credentials = load_credentials()
        except ConfigurationError:
            raise
        if canonical_data_dir(new_settings.data_dir) != canonical_data_dir(self.settings.data_dir):
            raise ConfigurationError(
                "data_dir_change_requires_restart",
                "changing the service data directory requires a service restart",
            )

        self.settings = new_settings
        self.idle_monitor.configure(new_settings.idle_timeout_seconds)
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

    async def active_work_summary(self) -> dict[str, int]:
        sessions = await self.repository.list_sessions()
        active_runs = sum(1 for item in sessions if item.phase is not SessionPhase.IDLE)
        pending_approvals = sum(
            1 for item in sessions if item.phase is SessionPhase.AWAITING_APPROVAL
        )
        return {
            "active_runs": active_runs,
            "pending_approvals": pending_approvals,
            "connected_event_streams": await self.event_bus.subscriber_count(),
        }

    async def request_shutdown(self, *, force: bool) -> int:
        sessions = await self.repository.list_sessions()
        active = [item for item in sessions if item.phase is not SessionPhase.IDLE]
        if active and not force:
            raise DomainConflict(
                f"service has {len(active)} active run(s); retry with --force to interrupt"
            )
        if force:
            for item in active:
                await self.manager.abort(item.session_id)
        self.shutdown_requested.set()
        return len(active)

    def lifecycle_metadata(self) -> dict[str, object]:
        owner = self.service_owner
        return {
            "service_version": __version__,
            "protocol_version": PROTOCOL_VERSION,
            "instance_id": (owner.instance_id if owner is not None else self.process_instance_id),
            "pid": owner.pid if owner is not None else os.getpid(),
            "started_at": owner.started_at if owner is not None else self.process_started_at,
            "data_dir": str(canonical_data_dir(self.settings.data_dir)),
            "base_url": owner.base_url if owner is not None else None,
            "managed": owner is not None,
        }


async def build_app_state(
    *,
    settings: Settings | None = None,
    credentials: Credentials | None = None,
    database_path: Path | None = None,
    runtime: AgentRuntime | None = None,
    require_server_token: bool = True,
    service_owner: ServiceOwner | None = None,
) -> AppState:
    settings = settings or load_settings()
    credentials = credentials or load_credentials()

    if require_server_token and not credentials.can_start_authenticated_api():
        raise ConfigurationError(
            "missing_server_token",
            "typed-code server token is required to start authenticated API routes",
        )

    owner = service_owner or ServiceOwner.acquire(settings.data_dir)
    settings.data_dir = owner.paths.data_dir
    database: Database | None = None
    try:
        db_path = database_path or (owner.paths.data_dir / "typed-code.db")
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
            service_owner=owner,
        )
    except BaseException:
        if database is not None:
            await database.close()
        owner.close()
        raise
