"""Non-sensitive settings loaded from ``config.toml`` with env fallback."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from typed_code.config.errors import ConfigurationError
from typed_code.config.paths import default_config_path, default_data_dir

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8741
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_CLIPROXY_BASE_URL = "http://127.0.0.1:8317/v1"
DEFAULT_PROVIDER: Literal["deepseek", "cliproxy"] = "cliproxy"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_BASH_EXECUTABLE = "/bin/bash"
DEFAULT_READ_MAX_BYTES = 256_000
DEFAULT_READ_MAX_LINES = 2_000
DEFAULT_BASH_MAX_STDOUT_BYTES = 256_000
DEFAULT_BASH_MAX_STDERR_BYTES = 256_000
DEFAULT_EVENT_RETENTION_COUNT = 2_000

ProviderName = Literal["deepseek", "cliproxy"]


class Settings(BaseModel):
    """Validated non-sensitive service settings."""

    host: str = DEFAULT_HOST
    port: int = Field(default=DEFAULT_PORT, ge=1, le=65535)
    data_dir: Path
    deepseek_base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    cliproxy_base_url: str = DEFAULT_CLIPROXY_BASE_URL
    default_provider: ProviderName = DEFAULT_PROVIDER
    default_model: str = DEFAULT_MODEL
    bash_executable: str = DEFAULT_BASH_EXECUTABLE
    read_max_bytes: int = Field(default=DEFAULT_READ_MAX_BYTES, ge=1)
    read_max_lines: int = Field(default=DEFAULT_READ_MAX_LINES, ge=1)
    bash_max_stdout_bytes: int = Field(default=DEFAULT_BASH_MAX_STDOUT_BYTES, ge=1)
    bash_max_stderr_bytes: int = Field(default=DEFAULT_BASH_MAX_STDERR_BYTES, ge=1)
    event_retention_count: int = Field(default=DEFAULT_EVENT_RETENTION_COUNT, ge=1)

    @field_validator("data_dir", mode="before")
    @classmethod
    def _expand_data_dir(cls, value: object) -> Path:
        if isinstance(value, Path):
            return value.expanduser()
        if isinstance(value, str):
            return Path(value).expanduser()
        raise TypeError("data_dir must be a path string")

    @field_validator("default_provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as exc:
        raise ConfigurationError(
            "config_read_failed",
            f"Failed to read configuration file at {path}: {exc.strerror or type(exc).__name__}",
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(
            "config_invalid_toml",
            f"Configuration file at {path} is not valid TOML: {exc}",
        ) from exc
    if not isinstance(data, dict):
        raise ConfigurationError(
            "config_invalid_shape",
            f"Configuration file at {path} must contain a TOML table at the root",
        )
    return data


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigurationError(
            "config_invalid_shape",
            f"Configuration section [{name}] must be a table",
        )
    return value


def _nested_provider_base_url(providers: dict[str, Any], name: str) -> str | None:
    block = providers.get(name)
    if block is None:
        return None
    if not isinstance(block, dict):
        raise ConfigurationError(
            "config_invalid_shape",
            f"Configuration section [providers.{name}] must be a table",
        )
    url = block.get("base_url")
    if url is None:
        return None
    if not isinstance(url, str) or not url.strip():
        raise ConfigurationError(
            "config_invalid_value",
            f"providers.{name}.base_url must be a non-empty string",
        )
    return url.strip()


def _file_value(mapping: dict[str, Any], key: str) -> object | None:
    if key not in mapping:
        return None
    return mapping[key]


def _env_str(environ: dict[str, str], key: str) -> str | None:
    value = environ.get(key)
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _env_int(environ: dict[str, str], key: str) -> int | None:
    raw = _env_str(environ, key)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(
            "config_invalid_value",
            f"Environment variable {key} must be an integer",
        ) from exc


def _first_str(*candidates: object | None, default: str) -> str:
    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        if not isinstance(candidate, str):
            raise ConfigurationError(
                "config_invalid_value",
                "Expected a string configuration value",
            )
    return default


def _first_int(*candidates: object | None, default: int) -> int:
    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, bool):
            raise ConfigurationError(
                "config_invalid_value",
                "Expected an integer configuration value",
            )
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str) and candidate.strip():
            try:
                return int(candidate.strip())
            except ValueError as exc:
                raise ConfigurationError(
                    "config_invalid_value",
                    "Expected an integer configuration value",
                ) from exc
        raise ConfigurationError(
            "config_invalid_value",
            "Expected an integer configuration value",
        )
    return default


def load_settings(
    *,
    config_path: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Settings:
    """Load non-sensitive settings with file-first precedence.

    Precedence for each field:
    1. value present in ``config.toml``
    2. matching environment variable, when the file field is absent
    3. built-in non-sensitive default
    """
    env = dict(os.environ if environ is None else environ)
    path = default_config_path(environ=env) if config_path is None else config_path

    file_data: dict[str, Any] = {}
    if path.is_file():
        file_data = _read_toml(path)

    listen = _section(file_data, "listen")
    data = _section(file_data, "data")
    providers = _section(file_data, "providers")
    defaults = _section(file_data, "defaults")
    bash = _section(file_data, "bash")
    limits = _section(file_data, "limits")

    data_dir_raw = _first_str(
        _file_value(data, "dir"),
        _env_str(env, "TYPED_CODE_DATA_DIR"),
        default=str(default_data_dir(environ=env)),
    )

    try:
        return Settings(
            host=_first_str(
                _file_value(listen, "host"),
                _env_str(env, "TYPED_CODE_HOST"),
                default=DEFAULT_HOST,
            ),
            port=_first_int(
                _file_value(listen, "port"),
                _env_int(env, "TYPED_CODE_PORT"),
                default=DEFAULT_PORT,
            ),
            data_dir=data_dir_raw,
            deepseek_base_url=_first_str(
                _nested_provider_base_url(providers, "deepseek"),
                _env_str(env, "TYPED_CODE_DEEPSEEK_BASE_URL"),
                default=DEFAULT_DEEPSEEK_BASE_URL,
            ),
            cliproxy_base_url=_first_str(
                _nested_provider_base_url(providers, "cliproxy"),
                _env_str(env, "TYPED_CODE_CLIPROXY_BASE_URL"),
                default=DEFAULT_CLIPROXY_BASE_URL,
            ),
            default_provider=_first_str(  # type: ignore[arg-type]
                _file_value(defaults, "provider"),
                _env_str(env, "TYPED_CODE_DEFAULT_PROVIDER"),
                default=DEFAULT_PROVIDER,
            ),
            default_model=_first_str(
                _file_value(defaults, "model"),
                _env_str(env, "TYPED_CODE_DEFAULT_MODEL"),
                default=DEFAULT_MODEL,
            ),
            bash_executable=_first_str(
                _file_value(bash, "executable"),
                _env_str(env, "TYPED_CODE_BASH_EXECUTABLE"),
                default=DEFAULT_BASH_EXECUTABLE,
            ),
            read_max_bytes=_first_int(
                _file_value(limits, "read_max_bytes"),
                _env_int(env, "TYPED_CODE_READ_MAX_BYTES"),
                default=DEFAULT_READ_MAX_BYTES,
            ),
            read_max_lines=_first_int(
                _file_value(limits, "read_max_lines"),
                _env_int(env, "TYPED_CODE_READ_MAX_LINES"),
                default=DEFAULT_READ_MAX_LINES,
            ),
            bash_max_stdout_bytes=_first_int(
                _file_value(limits, "bash_max_stdout_bytes"),
                _env_int(env, "TYPED_CODE_BASH_MAX_STDOUT_BYTES"),
                default=DEFAULT_BASH_MAX_STDOUT_BYTES,
            ),
            bash_max_stderr_bytes=_first_int(
                _file_value(limits, "bash_max_stderr_bytes"),
                _env_int(env, "TYPED_CODE_BASH_MAX_STDERR_BYTES"),
                default=DEFAULT_BASH_MAX_STDERR_BYTES,
            ),
            event_retention_count=_first_int(
                _file_value(limits, "event_retention_count"),
                _env_int(env, "TYPED_CODE_EVENT_RETENTION_COUNT"),
                default=DEFAULT_EVENT_RETENTION_COUNT,
            ),
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # validation / type errors become stable codes
        raise ConfigurationError(
            "config_invalid_value",
            f"Invalid configuration value: {exc}",
        ) from exc
