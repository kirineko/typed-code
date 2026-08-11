"""Ensure live smoke is not collected as default pytest tests."""

from __future__ import annotations

from pathlib import Path


def test_live_smoke_module_is_not_under_tests() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "src" / "typed_code" / "smoke" / "live.py").is_file()
    # No tests/live directory by default
    assert not (root / "tests" / "live").exists()
