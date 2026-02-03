"""SSE streaming utilities."""
import asyncio
import json
from typing import Any, AsyncGenerator
from datetime import datetime


def format_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format data as an SSE event string."""
    json_data = json.dumps({"type": event_type, "data": data})
    return f"data: {json_data}\n\n"


class SSEStreamManager:
    """Manages SSE event streaming for an investigation."""

    def __init__(self, investigation_id: str):
        self.investigation_id = investigation_id
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._closed = False
        self._tool_counter = 0

    async def emit_text(self, content: str) -> None:
        """Emit a text chunk event."""
        await self._emit("text", {"content": content})

    async def emit_tool_start(self, tool: str, input_data: dict) -> str:
        """Emit tool start event. Returns tool execution ID."""
        self._tool_counter += 1
        tool_id = f"{self.investigation_id}:tool:{self._tool_counter}"
        await self._emit("tool_start", {
            "id": tool_id,
            "tool": tool,
            "input": input_data,
        })
        return tool_id

    async def emit_tool_end(
        self,
        tool_id: str,
        tool: str,
        duration_ms: int,
        output: str | None = None,
    ) -> None:
        """Emit tool end event."""
        await self._emit("tool_end", {
            "id": tool_id,
            "tool": tool,
            "duration_ms": duration_ms,
            "output": output[:500] if output else None,  # Truncate output
        })

    async def emit_subagent_start(self, agent_type: str) -> None:
        """Emit sub-agent start event."""
        await self._emit("subagent_start", {"agent_type": agent_type})

    async def emit_subagent_end(
        self,
        agent_type: str,
        analysis: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Emit sub-agent end event."""
        await self._emit("subagent_end", {
            "agent_type": agent_type,
            "analysis": analysis[:2000] if analysis else "",  # Truncate
            "success": success,
            "error": error,
        })

    async def emit_search_progress(
        self,
        engine_name: str,
        status: str,
        results_count: int,
        total_engines: int,
        completed_engines: int,
        total_results: int,
        message: str,
    ) -> None:
        """Emit search progress event."""
        await self._emit("search_progress", {
            "engine_name": engine_name,
            "status": status,
            "results_count": results_count,
            "total_engines": total_engines,
            "completed_engines": completed_engines,
            "total_results": total_results,
            "message": message,
        })

    async def emit_complete(
        self,
        text: str,
        session_id: str | None = None,
        duration_ms: int | None = None,
        num_turns: int | None = None,
    ) -> None:
        """Emit investigation complete event."""
        await self._emit("complete", {
            "text": text,
            "session_id": session_id,
            "duration_ms": duration_ms,
            "num_turns": num_turns,
        })
        self._closed = True

    async def emit_error(self, message: str, code: str = "INVESTIGATION_ERROR") -> None:
        """Emit error event."""
        await self._emit("error", {"message": message, "code": code})
        self._closed = True

    async def _emit(self, event_type: str, data: dict) -> None:
        """Internal emit method."""
        if not self._closed:
            event = format_sse_event(event_type, data)
            await self.queue.put(event)

    async def stream(self) -> AsyncGenerator[str, None]:
        """Generate SSE events for streaming response."""
        try:
            while not self._closed:
                try:
                    event = await asyncio.wait_for(self.queue.get(), timeout=30.0)
                    yield event
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass

    def close(self) -> None:
        """Close the stream."""
        self._closed = True
