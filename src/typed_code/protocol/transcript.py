"""Normalized transcript items for authoritative snapshots."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from typed_code.protocol.common import ProtocolModel, ToolCallStatus, TranscriptItemType


class TranscriptItemBase(ProtocolModel):
    id: str
    created_at: str


class UserMessageItem(TranscriptItemBase):
    type: Literal[TranscriptItemType.USER_MESSAGE] = TranscriptItemType.USER_MESSAGE
    text: str


class AssistantMessageItem(TranscriptItemBase):
    type: Literal[TranscriptItemType.ASSISTANT_MESSAGE] = TranscriptItemType.ASSISTANT_MESSAGE
    text: str


class ThinkingItem(TranscriptItemBase):
    type: Literal[TranscriptItemType.THINKING] = TranscriptItemType.THINKING
    text: str


class ToolCallItem(TranscriptItemBase):
    type: Literal[TranscriptItemType.TOOL_CALL] = TranscriptItemType.TOOL_CALL
    tool_name: str
    summary: str
    status: ToolCallStatus
    args_preview: str | None = None


class ToolResultItem(TranscriptItemBase):
    type: Literal[TranscriptItemType.TOOL_RESULT] = TranscriptItemType.TOOL_RESULT
    tool_call_id: str
    ok: bool
    summary: str
    truncated: bool = False


class SystemNoticeItem(TranscriptItemBase):
    type: Literal[TranscriptItemType.SYSTEM_NOTICE] = TranscriptItemType.SYSTEM_NOTICE
    text: str
    kind: str | None = None


TranscriptItem = Annotated[
    UserMessageItem
    | AssistantMessageItem
    | ThinkingItem
    | ToolCallItem
    | ToolResultItem
    | SystemNoticeItem,
    Field(discriminator="type"),
]
