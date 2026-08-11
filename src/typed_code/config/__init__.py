"""Local XDG configuration and credential loading."""

from __future__ import annotations

from typed_code.config.credentials import (
    Credentials,
    ProviderAvailability,
    load_credentials,
)
from typed_code.config.errors import ConfigurationError
from typed_code.config.paths import config_dir, credentials_path, default_config_path
from typed_code.config.settings import Settings, load_settings

__all__ = [
    "ConfigurationError",
    "Credentials",
    "ProviderAvailability",
    "Settings",
    "config_dir",
    "credentials_path",
    "default_config_path",
    "load_credentials",
    "load_settings",
]
