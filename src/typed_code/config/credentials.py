"""Secret loading from ``credentials.toml`` with file-first precedence."""

from __future__ import annotations

import os
import stat
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, SecretStr

from typed_code.config.errors import ConfigurationError
from typed_code.config.paths import credentials_path

ProviderName = Literal["deepseek", "cliproxy"]

SERVER_TOKEN_ENV = "TYPED_CODE_SERVER_TOKEN"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
CLIPROXY_API_KEY_ENV = "CLIPROXY_API_KEY"


class ProviderAvailability(StrEnum):
    """Credential availability for a configured provider."""

    AVAILABLE = "available"
    MISSING_CREDENTIALS = "missing_credentials"


class Credentials(BaseModel):
    """Resolved secrets and derived availability flags.

    Secret values are stored as ``SecretStr`` so accidental stringification does
    not leak credentials into logs or exceptions.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    server_token: SecretStr | None = None
    deepseek_api_key: SecretStr | None = None
    cliproxy_api_key: SecretStr | None = None
    server_token_present: bool = False
    deepseek_availability: ProviderAvailability = ProviderAvailability.MISSING_CREDENTIALS
    cliproxy_availability: ProviderAvailability = ProviderAvailability.MISSING_CREDENTIALS

    def provider_availability(self, provider: ProviderName) -> ProviderAvailability:
        if provider == "deepseek":
            return self.deepseek_availability
        return self.cliproxy_availability

    def can_start_authenticated_api(self) -> bool:
        """Return whether authenticated API routes may start."""
        return self.server_token_present and self.server_token is not None

    def require_server_token(self) -> SecretStr:
        """Return the server token or raise a secret-safe configuration error."""
        if self.server_token is None or not self.server_token_present:
            raise ConfigurationError(
                "missing_server_token",
                "typed-code server token is absent from credentials.toml and "
                f"{SERVER_TOKEN_ENV}; authenticated API routes cannot start",
            )
        return self.server_token


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as exc:
        raise ConfigurationError(
            "credentials_read_failed",
            f"Failed to read credentials file at {path}: {exc.strerror or type(exc).__name__}",
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(
            "credentials_invalid_toml",
            f"Credentials file at {path} is not valid TOML",
        ) from exc
    if not isinstance(data, dict):
        raise ConfigurationError(
            "credentials_invalid_shape",
            f"Credentials file at {path} must contain a TOML table at the root",
        )
    return data


def _validate_credentials_file_permissions(path: Path) -> None:
    """Enforce regular file, current-user ownership, and mode ``0600``."""
    try:
        st = path.lstat()
    except OSError as exc:
        raise ConfigurationError(
            "credentials_read_failed",
            f"Failed to stat credentials file at {path}: {exc.strerror or type(exc).__name__}",
        ) from exc

    if stat.S_ISLNK(st.st_mode):
        raise ConfigurationError(
            "credentials_unsafe_permissions",
            f"Credentials path {path} must be a regular file, not a symbolic link",
        )
    if not stat.S_ISREG(st.st_mode):
        raise ConfigurationError(
            "credentials_unsafe_permissions",
            f"Credentials path {path} must be a regular file",
        )

    if st.st_uid != os.getuid():
        raise ConfigurationError(
            "credentials_unsafe_permissions",
            f"Credentials file at {path} must be owned by the current user",
        )

    mode = stat.S_IMODE(st.st_mode)
    if mode & 0o077:
        raise ConfigurationError(
            "credentials_unsafe_permissions",
            f"Credentials file at {path} has unsafe permissions "
            f"(mode {mode:04o}); required mode is 0600",
        )


def _optional_secret_from_file(data: dict[str, Any], key: str) -> str | None:
    if key not in data:
        return None
    value = data[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigurationError(
            "credentials_invalid_value",
            f"Credential field {key} must be a string when present",
        )
    stripped = value.strip()
    return stripped if stripped else None


def _optional_secret_from_env(environ: dict[str, str], key: str) -> str | None:
    value = environ.get(key)
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _resolve_secret(
    *,
    file_value: str | None,
    env_value: str | None,
) -> str | None:
    """File value wins when present; environment fills only when file field is absent."""
    if file_value is not None:
        return file_value
    return env_value


def _as_secret(value: str | None) -> SecretStr | None:
    return SecretStr(value) if value is not None else None


def _availability(value: str | None) -> ProviderAvailability:
    if value is None:
        return ProviderAvailability.MISSING_CREDENTIALS
    return ProviderAvailability.AVAILABLE


def load_credentials(
    *,
    path: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Credentials:
    """Load secrets with file-first precedence and permission enforcement.

    A missing credentials file is allowed: environment variables and missing
    states still resolve. An existing credentials file with unsafe permissions
    is refused without loading any secrets from it.
    """
    env = dict(os.environ if environ is None else environ)
    cred_path = credentials_path(environ=env) if path is None else path

    file_data: dict[str, Any] = {}
    if cred_path.exists():
        _validate_credentials_file_permissions(cred_path)
        file_data = _read_toml(cred_path)

    server_token = _resolve_secret(
        file_value=_optional_secret_from_file(file_data, "server_token"),
        env_value=_optional_secret_from_env(env, SERVER_TOKEN_ENV),
    )
    deepseek_key = _resolve_secret(
        file_value=_optional_secret_from_file(file_data, "deepseek_api_key"),
        env_value=_optional_secret_from_env(env, DEEPSEEK_API_KEY_ENV),
    )
    cliproxy_key = _resolve_secret(
        file_value=_optional_secret_from_file(file_data, "cliproxy_api_key"),
        env_value=_optional_secret_from_env(env, CLIPROXY_API_KEY_ENV),
    )

    return Credentials(
        server_token=_as_secret(server_token),
        deepseek_api_key=_as_secret(deepseek_key),
        cliproxy_api_key=_as_secret(cliproxy_key),
        server_token_present=server_token is not None,
        deepseek_availability=_availability(deepseek_key),
        cliproxy_availability=_availability(cliproxy_key),
    )


def ensure_config_dir(path: Path) -> None:
    """Create a configuration directory with mode ``0700`` when missing."""
    if path.exists():
        if not path.is_dir():
            raise ConfigurationError(
                "config_dir_invalid",
                f"Configuration path {path} exists and is not a directory",
            )
        return
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
