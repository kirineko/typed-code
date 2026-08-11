"""Tests for credentials.toml loading and permission enforcement."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from typed_code.config.credentials import (
    CLIPROXY_API_KEY_ENV,
    DEEPSEEK_API_KEY_ENV,
    SERVER_TOKEN_ENV,
    ProviderAvailability,
    load_credentials,
)
from typed_code.config.errors import ConfigurationError


def _write_creds(path: Path, content: str, mode: int = 0o600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.chmod(path, mode)
    return path


def test_file_credentials_override_environment(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    cred_path = config_home / "typed-code" / "credentials.toml"
    _write_creds(
        cred_path,
        """
server_token = "file-token"
deepseek_api_key = "file-deepseek"
cliproxy_api_key = "file-cliproxy"
""".strip()
        + "\n",
    )

    environ = {
        "XDG_CONFIG_HOME": str(config_home),
        SERVER_TOKEN_ENV: "env-token",
        DEEPSEEK_API_KEY_ENV: "env-deepseek",
        CLIPROXY_API_KEY_ENV: "env-cliproxy",
    }

    creds = load_credentials(environ=environ)

    assert creds.server_token is not None
    assert creds.server_token.get_secret_value() == "file-token"
    assert creds.deepseek_api_key is not None
    assert creds.deepseek_api_key.get_secret_value() == "file-deepseek"
    assert creds.cliproxy_api_key is not None
    assert creds.cliproxy_api_key.get_secret_value() == "file-cliproxy"
    assert creds.can_start_authenticated_api() is True
    assert creds.deepseek_availability is ProviderAvailability.AVAILABLE
    assert creds.cliproxy_availability is ProviderAvailability.AVAILABLE


def test_environment_fills_missing_credential_fields(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    cred_path = config_home / "typed-code" / "credentials.toml"
    _write_creds(
        cred_path,
        """
server_token = "file-token"
""".strip()
        + "\n",
    )

    environ = {
        "XDG_CONFIG_HOME": str(config_home),
        DEEPSEEK_API_KEY_ENV: "env-deepseek",
    }

    creds = load_credentials(environ=environ)

    assert creds.server_token is not None
    assert creds.server_token.get_secret_value() == "file-token"
    assert creds.deepseek_api_key is not None
    assert creds.deepseek_api_key.get_secret_value() == "env-deepseek"
    assert creds.deepseek_availability is ProviderAvailability.AVAILABLE
    assert creds.cliproxy_availability is ProviderAvailability.MISSING_CREDENTIALS


def test_missing_provider_keys_mark_missing_credentials(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    environ = {
        "XDG_CONFIG_HOME": str(config_home),
        SERVER_TOKEN_ENV: "env-token",
    }

    creds = load_credentials(environ=environ)

    assert creds.can_start_authenticated_api() is True
    assert creds.deepseek_availability is ProviderAvailability.MISSING_CREDENTIALS
    assert creds.cliproxy_availability is ProviderAvailability.MISSING_CREDENTIALS
    assert creds.provider_availability("deepseek") is ProviderAvailability.MISSING_CREDENTIALS


def test_missing_server_token_blocks_authenticated_api(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    environ = {
        "XDG_CONFIG_HOME": str(config_home),
        DEEPSEEK_API_KEY_ENV: "env-deepseek",
    }

    creds = load_credentials(environ=environ)

    assert creds.can_start_authenticated_api() is False
    with pytest.raises(ConfigurationError) as exc_info:
        creds.require_server_token()
    assert exc_info.value.code == "missing_server_token"
    assert "env-deepseek" not in exc_info.value.message
    assert "env-deepseek" not in str(exc_info.value)


def test_unsafe_permissions_refuse_file_without_leaking_secrets(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    cred_path = config_home / "typed-code" / "credentials.toml"
    secret = "super-secret-token-value"
    _write_creds(
        cred_path,
        f"""
server_token = "{secret}"
deepseek_api_key = "leaky-key"
""".strip()
        + "\n",
        mode=0o644,
    )

    environ = {
        "XDG_CONFIG_HOME": str(config_home),
        SERVER_TOKEN_ENV: "env-token",
    }

    with pytest.raises(ConfigurationError) as exc_info:
        load_credentials(environ=environ)

    assert exc_info.value.code == "credentials_unsafe_permissions"
    assert secret not in exc_info.value.message
    assert "leaky-key" not in exc_info.value.message
    assert "env-token" not in exc_info.value.message


def test_group_writable_credentials_are_rejected(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    cred_path = config_home / "typed-code" / "credentials.toml"
    _write_creds(
        cred_path,
        'server_token = "file-token"\n',
        mode=0o660,
    )

    with pytest.raises(ConfigurationError) as exc_info:
        load_credentials(environ={"XDG_CONFIG_HOME": str(config_home)})

    assert exc_info.value.code == "credentials_unsafe_permissions"


def test_symlink_credentials_are_rejected(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    real = tmp_path / "real-credentials.toml"
    real.write_text('server_token = "file-token"\n', encoding="utf-8")
    os.chmod(real, 0o600)

    cred_path = config_home / "typed-code" / "credentials.toml"
    cred_path.parent.mkdir(parents=True, exist_ok=True)
    cred_path.symlink_to(real)

    with pytest.raises(ConfigurationError) as exc_info:
        load_credentials(environ={"XDG_CONFIG_HOME": str(config_home)})

    assert exc_info.value.code == "credentials_unsafe_permissions"


def test_secret_str_repr_does_not_expose_value(tmp_path: Path) -> None:
    config_home = tmp_path / "config"
    cred_path = config_home / "typed-code" / "credentials.toml"
    secret = "do-not-print-me"
    _write_creds(cred_path, f'server_token = "{secret}"\n')

    creds = load_credentials(environ={"XDG_CONFIG_HOME": str(config_home)})

    assert secret not in repr(creds)
    assert secret not in str(creds)
