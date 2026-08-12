"""Browser-origin and loopback-host boundary reserved for a future local Web UI."""

from __future__ import annotations

import ipaddress
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import Response

from typed_code.api.errors import structured_error_response
from typed_code.protocol.errors import ErrorCode


async def enforce_browser_boundary(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Reject DNS-rebinding and cross-origin browser requests before routing."""
    state = request.app.state.app_state
    owner = state.service_owner
    host = request.headers.get("host", "")
    if owner is not None and owner.base_url is not None and not _is_loopback_host(host):
        return structured_error_response(
            403,
            ErrorCode.UNAUTHORIZED,
            "request host is not an allowed loopback service origin",
        )

    origin = request.headers.get("origin")
    if origin is not None and not _same_origin(
        origin,
        scheme=request.url.scheme,
        host=host,
    ):
        return structured_error_response(
            403,
            ErrorCode.UNAUTHORIZED,
            "cross-origin browser request rejected",
        )
    return await call_next(request)


def _is_loopback_host(authority: str) -> bool:
    try:
        hostname = urlsplit(f"//{authority}").hostname
    except ValueError:
        return False
    if not hostname:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _same_origin(origin: str, *, scheme: str, host: str) -> bool:
    try:
        candidate = urlsplit(origin)
        expected = urlsplit(f"{scheme}://{host}")
        return (
            candidate.scheme.lower(),
            candidate.hostname,
            _effective_port(candidate.scheme, candidate.port),
        ) == (
            expected.scheme.lower(),
            expected.hostname,
            _effective_port(expected.scheme, expected.port),
        )
    except ValueError:
        return False


def _effective_port(scheme: str, port: int | None) -> int | None:
    if port is not None:
        return port
    if scheme.lower() == "http":
        return 80
    if scheme.lower() == "https":
        return 443
    return None
