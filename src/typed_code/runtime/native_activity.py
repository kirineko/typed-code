"""Map Pydantic AI native web-search parts onto public tool activity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import NativeToolCallPart, NativeToolReturnPart

from typed_code.runtime.native_tools import (
    NATIVE_WEB_SEARCH_NAME,
    web_search_call_summary,
    web_search_result_summary,
)


@dataclass
class NativeSearchActivity:
    """Publish sanitized web_search lifecycle events for one agent stream."""

    _ids: dict[int, str] = field(default_factory=dict)
    _summaries: dict[str, str] = field(default_factory=dict)
    _started: set[str] = field(default_factory=set)

    async def observe_start(
        self, repository: Any, session_id: str, index: int, part: object
    ) -> None:
        if isinstance(part, NativeToolCallPart):
            await self._start_call(repository, session_id, index, part)
            return
        if isinstance(part, NativeToolReturnPart):
            await self._finish_return(repository, session_id, index, part)

    async def observe_end(
        self, repository: Any, session_id: str, index: int, part: object
    ) -> None:
        if isinstance(part, NativeToolCallPart):
            self._remember_call(index, part)
            return
        if isinstance(part, NativeToolReturnPart):
            await self._finish_return(repository, session_id, index, part)

    def _remember_call(self, index: int, part: NativeToolCallPart) -> str | None:
        if part.tool_name != NATIVE_WEB_SEARCH_NAME:
            return None
        tool_call_id = part.tool_call_id or part.id or f"web_search:{index}"
        self._ids[index] = tool_call_id
        summary = web_search_call_summary(part.args)
        if summary != "web search" or tool_call_id not in self._summaries:
            self._summaries[tool_call_id] = summary
        return tool_call_id

    async def _start_call(
        self, repository: Any, session_id: str, index: int, part: NativeToolCallPart
    ) -> None:
        tool_call_id = self._remember_call(index, part)
        if tool_call_id is None or tool_call_id in self._started:
            return
        self._started.add(tool_call_id)
        await repository.record_tool_started(
            session_id,
            tool_call_id=tool_call_id,
            tool_name=NATIVE_WEB_SEARCH_NAME,
            summary=self._summaries[tool_call_id],
        )

    async def _finish_return(
        self,
        repository: Any,
        session_id: str,
        index: int,
        part: NativeToolReturnPart,
    ) -> None:
        if part.tool_name != NATIVE_WEB_SEARCH_NAME:
            return
        tool_call_id = part.tool_call_id or self._ids.get(index) or f"web_search:{index}"
        if tool_call_id not in self._started:
            await repository.record_tool_started(
                session_id,
                tool_call_id=tool_call_id,
                tool_name=NATIVE_WEB_SEARCH_NAME,
                summary=self._summaries.get(tool_call_id, "web search"),
            )
            self._started.add(tool_call_id)
        ok = part.outcome != "failure"
        await repository.finish_tool(
            session_id,
            tool_call_id=tool_call_id,
            tool_name=NATIVE_WEB_SEARCH_NAME,
            summary=web_search_result_summary(part.content, ok=ok),
            ok=ok,
            call_summary=self._summaries.get(tool_call_id),
        )
        self._ids.pop(index, None)
        self._summaries.pop(tool_call_id, None)
        self._started.discard(tool_call_id)
