"""Service health and lifecycle protocol models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from typed_code.protocol.common import PROTOCOL_VERSION, ProtocolModel, ProtocolVersion


class ActiveWorkSummary(ProtocolModel):
    active_runs: int = Field(ge=0)
    pending_approvals: int = Field(ge=0)
    connected_event_streams: int = Field(ge=0)


class ServiceStopRequest(ProtocolModel):
    force: bool = False


class ServiceStopResponse(ProtocolModel):
    status: Literal["stopping"] = "stopping"
    forced: bool
    interrupted_runs: int = Field(ge=0)


class ServiceHealth(ProtocolModel):
    service_version: str
    protocol_version: ProtocolVersion = PROTOCOL_VERSION
    instance_id: str
    pid: int = Field(ge=1)
    started_at: str
    data_dir: str
    base_url: str | None = None
    managed: bool
    active_work: ActiveWorkSummary


class BashHealth(ProtocolModel):
    ready: bool
    executable: str | None = None


class HealthResponse(ProtocolModel):
    status: Literal["ok"] = "ok"
    protocol_version: ProtocolVersion = PROTOCOL_VERSION
    service: ServiceHealth
    providers: dict[str, str]
    bash: BashHealth
    default_provider: str | None = None
    default_model: str | None = None
