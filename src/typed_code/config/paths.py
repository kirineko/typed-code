"""XDG path resolution for typed-code configuration."""

from __future__ import annotations

import os
from pathlib import Path


def _expand_home(path: str) -> Path:
    return Path(path).expanduser()


def config_dir(*, environ: dict[str, str] | None = None) -> Path:
    """Return ``${XDG_CONFIG_HOME:-~/.config}/typed-code``."""
    env = os.environ if environ is None else environ
    xdg = env.get("XDG_CONFIG_HOME")
    if xdg:
        return _expand_home(xdg) / "typed-code"
    return Path.home() / ".config" / "typed-code"


def default_config_path(*, environ: dict[str, str] | None = None) -> Path:
    return config_dir(environ=environ) / "config.toml"


def credentials_path(*, environ: dict[str, str] | None = None) -> Path:
    return config_dir(environ=environ) / "credentials.toml"


def default_data_dir(*, environ: dict[str, str] | None = None) -> Path:
    """Return ``${XDG_DATA_HOME:-~/.local/share}/typed-code``."""
    env = os.environ if environ is None else environ
    xdg = env.get("XDG_DATA_HOME")
    if xdg:
        return _expand_home(xdg) / "typed-code"
    return Path.home() / ".local" / "share" / "typed-code"
