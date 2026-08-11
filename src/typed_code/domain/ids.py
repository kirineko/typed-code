"""Opaque identifier generation."""

from __future__ import annotations

from uuid import uuid4


def new_id() -> str:
    return uuid4().hex


def new_session_id() -> str:
    return new_id()


def new_run_id() -> str:
    return new_id()


def new_approval_id() -> str:
    return new_id()


def new_transcript_item_id() -> str:
    return new_id()


def new_message_id() -> str:
    return new_id()
