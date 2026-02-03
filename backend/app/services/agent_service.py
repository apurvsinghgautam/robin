"""Agent service wrapping RobinAgent for API use."""
import asyncio
import sys
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

# Add parent robin directory to path for imports
robin_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(robin_root))

from agent import RobinAgent, InvestigationResult
from agent.tools import set_search_progress_callback
from core.search import SearchProgress
from ..sse.stream import SSEStreamManager
from ..config import get_settings

settings = get_settings()


class AgentService:
    """
    Wraps RobinAgent to provide API-friendly interface with SSE streaming.

    Converts RobinAgent callbacks into SSE events for real-time frontend updates.
    """

    def __init__(
        self,
        investigation_id: UUID,
        stream_manager: SSEStreamManager,
        model: Optional[str] = None,
    ):
        self.investigation_id = investigation_id
        self.stream = stream_manager
        self.model = model or settings.default_model

        self._current_tool_id: Optional[str] = None
        self._tool_start_time: float = 0
        self._tools_used: list[dict] = []
        self._subagent_results: list[dict] = []
        self._full_response: str = ""
        self._result: Optional[InvestigationResult] = None

        # Event loop reference for cross-thread callbacks
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Create agent with callbacks
        self._agent = RobinAgent(
            on_text=self._on_text,
            on_tool_use=self._on_tool_use,
            on_complete=self._on_complete,
            model=self.model,
        )

    def _on_search_progress(self, progress: SearchProgress) -> None:
        """Callback for search progress - emit SSE event (called from thread pool)."""
        print(f"[DEBUG] Search progress: {progress.engine_name} - {progress.status} - {progress.message}")

        if self._loop is None:
            print("[DEBUG] No event loop, skipping progress emit")
            return

        # Schedule the async emit on the main event loop
        asyncio.run_coroutine_threadsafe(
            self.stream.emit_search_progress(
                engine_name=progress.engine_name,
                status=progress.status,
                results_count=progress.results_count,
                total_engines=progress.total_engines,
                completed_engines=progress.completed_engines,
                total_results=progress.total_results,
                message=progress.message,
            ),
            self._loop
        )

    def _on_text(self, text: str) -> None:
        """Callback for streaming text - emit SSE event."""
        self._full_response += text
        # Schedule async emit
        asyncio.create_task(self.stream.emit_text(text))

    def _on_tool_use(self, name: str, input_data: dict) -> None:
        """Callback for tool use - emit SSE event."""
        # End previous tool if still running
        if self._current_tool_id:
            duration = int((time.time() - self._tool_start_time) * 1000)
            asyncio.create_task(
                self.stream.emit_tool_end(
                    self._current_tool_id,
                    self._tools_used[-1]["name"],
                    duration,
                )
            )

        # Start new tool
        self._tool_start_time = time.time()
        self._tools_used.append({"name": name, "input": input_data})

        async def emit_start():
            self._current_tool_id = await self.stream.emit_tool_start(name, input_data)
            # Check for sub-agent delegation
            if name == "mcp__robin__delegate_analysis":
                agent_types = input_data.get("agent_types", [])
                for agent_type in agent_types:
                    await self.stream.emit_subagent_start(agent_type)

        asyncio.create_task(emit_start())

    def _on_complete(self, result: InvestigationResult) -> None:
        """Callback for completion - emit SSE event."""
        self._result = result

        # End any running tool
        if self._current_tool_id:
            duration = int((time.time() - self._tool_start_time) * 1000)
            asyncio.create_task(
                self.stream.emit_tool_end(
                    self._current_tool_id,
                    self._tools_used[-1]["name"] if self._tools_used else "unknown",
                    duration,
                )
            )

        asyncio.create_task(
            self.stream.emit_complete(
                text=result.text,
                session_id=result.session_id,
                duration_ms=result.duration_ms,
                num_turns=result.num_turns,
            )
        )

    async def investigate(self, query: str) -> InvestigationResult:
        """
        Run an investigation and stream results via SSE.

        Args:
            query: The investigation query

        Returns:
            InvestigationResult with full response and metadata
        """
        # Store event loop for cross-thread callbacks
        self._loop = asyncio.get_running_loop()

        # Set search progress callback
        set_search_progress_callback(self._on_search_progress)

        try:
            async for _ in self._agent.investigate(query):
                # Yield control so SSE emit tasks can run
                await asyncio.sleep(0)

            # Give time for any pending emit tasks to complete
            await asyncio.sleep(0.1)

            return self._result or InvestigationResult(text=self._full_response)

        except Exception as e:
            await self.stream.emit_error(str(e))
            raise
        finally:
            # Clear the callback
            set_search_progress_callback(None)

    async def follow_up(self, query: str) -> InvestigationResult:
        """
        Send a follow-up query in the same session.

        Args:
            query: The follow-up query

        Returns:
            InvestigationResult with response
        """
        self._full_response = ""  # Reset for new response

        # Store event loop for cross-thread callbacks
        self._loop = asyncio.get_running_loop()

        # Set search progress callback
        set_search_progress_callback(self._on_search_progress)

        try:
            async for _ in self._agent.follow_up(query):
                # Yield control so SSE emit tasks can run
                await asyncio.sleep(0)

            # Give time for any pending emit tasks to complete
            await asyncio.sleep(0.1)

            return self._result or InvestigationResult(text=self._full_response)

        except Exception as e:
            await self.stream.emit_error(str(e))
            raise
        finally:
            # Clear the callback
            set_search_progress_callback(None)

    @property
    def session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._agent.session_id

    @property
    def tools_used(self) -> list[dict]:
        """Get list of tools used in this investigation."""
        return self._tools_used

    @property
    def full_response(self) -> str:
        """Get the full response text."""
        return self._full_response


# Cache for active agent sessions
_active_agents: dict[str, AgentService] = {}


def get_agent(investigation_id: UUID) -> Optional[AgentService]:
    """Get an active agent by investigation ID."""
    return _active_agents.get(str(investigation_id))


def set_agent(investigation_id: UUID, agent: AgentService) -> None:
    """Store an active agent."""
    _active_agents[str(investigation_id)] = agent


def remove_agent(investigation_id: UUID) -> None:
    """Remove an agent from cache."""
    _active_agents.pop(str(investigation_id), None)
