"""Tests for non-sensitive XDG config.toml loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from typed_code.config.errors import ConfigurationError
from typed_code.config.settings import (
    DEFAULT_CLIPROXY_BASE_URL,
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_HOST,
    DEFAULT_MODEL,
    DEFAULT_PORT,
    DEFAULT_PROVIDER,
    load_settings,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_defaults_without_file_or_env(tmp_path: Path) -> None:
    environ = {
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
    }
    settings = load_settings(environ=environ)

    assert settings.host == DEFAULT_HOST
    assert settings.port == DEFAULT_PORT
    assert settings.deepseek_base_url == DEFAULT_DEEPSEEK_BASE_URL
    assert settings.cliproxy_base_url == DEFAULT_CLIPROXY_BASE_URL
    assert settings.default_provider == DEFAULT_PROVIDER
    assert settings.default_model == DEFAULT_MODEL
    assert settings.default_model == "gpt-5.6-terra"
    assert settings.data_dir == tmp_path / "data" / "typed-code"
    assert settings.bash_executable == "/bin/bash"
    assert settings.idle_timeout_seconds is None
    assert settings.native_web_search is True


def test_config_file_overrides_environment(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    config_path = config_home / "typed-code" / "config.toml"
    _write(
        config_path,
        """
[listen]
host = "127.0.0.2"
port = 9001

[data]
dir = "/tmp/typed-code-data-from-file"

[providers.deepseek]
base_url = "https://deepseek.example/from-file"

[providers.cliproxy]
base_url = "http://127.0.0.1:9000/v1"

[defaults]
provider = "deepseek"
model = "deepseek-v4-flash"

[bash]
executable = "/usr/local/bin/bash"

[service]
idle_timeout_seconds = 42

[limits]
read_max_bytes = 111
read_max_lines = 22
bash_max_stdout_bytes = 333
bash_max_stderr_bytes = 444
event_retention_count = 55
""".strip()
        + "\n",
    )

    environ = {
        "XDG_CONFIG_HOME": str(config_home),
        "TYPED_CODE_HOST": "10.0.0.1",
        "TYPED_CODE_PORT": "8000",
        "TYPED_CODE_DATA_DIR": "/tmp/env-data",
        "TYPED_CODE_DEEPSEEK_BASE_URL": "https://deepseek.example/from-env",
        "TYPED_CODE_CLIPROXY_BASE_URL": "http://env/v1",
        "TYPED_CODE_DEFAULT_PROVIDER": "cliproxy",
        "TYPED_CODE_DEFAULT_MODEL": "env-model",
        "TYPED_CODE_BASH_EXECUTABLE": "/bin/env-bash",
        "TYPED_CODE_READ_MAX_BYTES": "999",
        "TYPED_CODE_READ_MAX_LINES": "99",
        "TYPED_CODE_BASH_MAX_STDOUT_BYTES": "999",
        "TYPED_CODE_BASH_MAX_STDERR_BYTES": "999",
        "TYPED_CODE_EVENT_RETENTION_COUNT": "999",
        "TYPED_CODE_IDLE_TIMEOUT_SECONDS": "99",
    }

    settings = load_settings(environ=environ)

    assert settings.host == "127.0.0.2"
    assert settings.port == 9001
    assert settings.data_dir == Path("/tmp/typed-code-data-from-file")
    assert settings.deepseek_base_url == "https://deepseek.example/from-file"
    assert settings.cliproxy_base_url == "http://127.0.0.1:9000/v1"
    assert settings.default_provider == "deepseek"
    assert settings.default_model == "deepseek-v4-flash"
    assert settings.bash_executable == "/usr/local/bin/bash"
    assert settings.read_max_bytes == 111
    assert settings.read_max_lines == 22
    assert settings.bash_max_stdout_bytes == 333
    assert settings.bash_max_stderr_bytes == 444
    assert settings.event_retention_count == 55
    assert settings.idle_timeout_seconds == 42
    assert settings.native_web_search is True


def test_environment_fills_missing_file_fields(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    config_path = config_home / "typed-code" / "config.toml"
    _write(
        config_path,
        """
[listen]
host = "127.0.0.3"
""".strip()
        + "\n",
    )

    environ = {
        "XDG_CONFIG_HOME": str(config_home),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "TYPED_CODE_PORT": "8123",
        "TYPED_CODE_DEFAULT_MODEL": "from-env",
    }

    settings = load_settings(environ=environ)

    assert settings.host == "127.0.0.3"
    assert settings.port == 8123
    assert settings.default_model == "from-env"
    assert settings.default_provider == DEFAULT_PROVIDER

    assert (
        load_settings(
            environ={
                "XDG_CONFIG_HOME": str(tmp_path / "missing-config"),
                "TYPED_CODE_IDLE_TIMEOUT_SECONDS": "0",
            }
        ).idle_timeout_seconds
        is None
    )


def test_invalid_toml_raises_configuration_error(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    config_path = config_home / "typed-code" / "config.toml"
    _write(config_path, "listen = [unterminated\n")

    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(environ={"XDG_CONFIG_HOME": str(config_home)})

    assert exc_info.value.code == "config_invalid_toml"


def test_invalid_provider_name_rejected(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    config_path = config_home / "typed-code" / "config.toml"
    _write(
        config_path,
        """
[defaults]
provider = "openai"
""".strip()
        + "\n",
    )

    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(environ={"XDG_CONFIG_HOME": str(config_home)})

    assert exc_info.value.code == "config_invalid_value"


def test_native_web_search_file_overrides_env(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    _write(
        config_home / "typed-code" / "config.toml",
        """
[tools]
native_web_search = false
""".strip()
        + "\n",
    )
    settings = load_settings(
        environ={
            "XDG_CONFIG_HOME": str(config_home),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "TYPED_CODE_NATIVE_WEB_SEARCH": "true",
        }
    )
    assert settings.native_web_search is False


def test_native_web_search_env_when_file_omits(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    _write(
        config_home / "typed-code" / "config.toml",
        """
[listen]
host = "127.0.0.4"
""".strip()
        + "\n",
    )
    settings = load_settings(
        environ={
            "XDG_CONFIG_HOME": str(config_home),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "TYPED_CODE_NATIVE_WEB_SEARCH": "false",
        }
    )
    assert settings.native_web_search is False
