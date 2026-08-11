"""Sanity checks for package layout and import boundaries."""

from __future__ import annotations

import importlib
from pathlib import Path

import typed_code

EXPECTED_PACKAGES = (
    "typed_code.api",
    "typed_code.approvals",
    "typed_code.compaction",
    "typed_code.config",
    "typed_code.domain",
    "typed_code.persistence",
    "typed_code.protocol",
    "typed_code.providers",
    "typed_code.runtime",
    "typed_code.workspace",
)


def test_version_exported() -> None:
    assert typed_code.__version__ == "0.1.0"


def test_boundary_packages_import() -> None:
    for name in EXPECTED_PACKAGES:
        module = importlib.import_module(name)
        assert module is not None


def test_protocol_version_constant() -> None:
    from typed_code.protocol import PROTOCOL_VERSION

    assert PROTOCOL_VERSION == 1


def test_reference_tree_is_not_importable_source() -> None:
    """typed-code must not ship or import reference project modules."""
    src_root = Path(typed_code.__file__).resolve().parent
    assert "reference" not in src_root.parts
