"""Robin Agent client using Anthropic SDK directly."""
import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional

import anthropic

from .prompts import ROBIN_SYSTEM_PROMPT
from .tools import TOOL_DEFINITIONS, execute_tool
from config import DEFAULT_MODEL, MAX_AGENT_TURNS


@dataclass
class InvestigationResult:
    """Result of an investigation query."""
    text: str
    session_id: Optional[str] = None
    duration_ms: Optional[int] = None
    num_turns: Optional[int] = None
    tools_used: list = field(default_factory=list)


class RobinAgent:
    """
    Autonomous dark web OSINT agent using Anthropic SDK.

    Provides:
    - Dark web search and scraping via custom tools
    - Streaming responses with callbacks
    - Tool use handling
    """

    def __init__(
        self,
        on_text: Optional[Callable[[str], None]] = None,
        on_tool_use: Optional[Callable[[str, dict], None]] = None,
        on_complete: Optional[Callable[[InvestigationResult], None]] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize RobinAgent.

        Args:
            on_text: Callback for streaming text chunks
            on_tool_use: Callback when a tool is invoked
            on_complete: Callback when investigation completes
            model: Claude model to use (default from config)
        """
        self.on_text = on_text
        self.on_tool_use = on_tool_use
        self.on_complete = on_complete
        self.model = model or DEFAULT_MODEL
        self.session_id: Optional[str] = None
        self._tools_used: list = []
        self._messages: list = []
        self._client = anthropic.Anthropic()

    def _get_tools(self) -> list[dict]:
        """Get tool definitions for Claude API."""
        return TOOL_DEFINITIONS

    async def investigate(
        self,
        query_text: str,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        """
        Run an OSINT investigation query.

        The agent autonomously decides:
        - How to refine the query
        - Which search engines to use
        - Which results to scrape
        - How to analyze findings

        Args:
            query_text: The investigation query (e.g., "ransomware payments 2024")
            stream: Whether to stream responses (default True)

        Yields:
            Text chunks as they arrive (if streaming)
        """
        import time
        start_time = time.time()

        self._tools_used = []
        full_response = ""
        num_turns = 0

        # Add user message
        self._messages.append({
            "role": "user",
            "content": query_text
        })

        tools = self._get_tools()

        while num_turns < MAX_AGENT_TURNS:
            num_turns += 1

            # Call Claude API with streaming
            with self._client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=ROBIN_SYSTEM_PROMPT,
                messages=self._messages,
                tools=tools,
            ) as stream_response:

                assistant_content = []
                current_text = ""
                tool_uses = []

                for event in stream_response:
                    if event.type == "content_block_start":
                        if event.content_block.type == "text":
                            current_text = ""
                        elif event.content_block.type == "tool_use":
                            tool_uses.append({
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": ""
                            })

                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            text = event.delta.text
                            current_text += text
                            full_response += text
                            if self.on_text:
                                self.on_text(text)
                            if stream:
                                yield text
                        elif hasattr(event.delta, "partial_json"):
                            if tool_uses:
                                tool_uses[-1]["input"] += event.delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_text:
                            assistant_content.append({
                                "type": "text",
                                "text": current_text
                            })
                            current_text = ""

                # Process any tool uses
                for tool in tool_uses:
                    try:
                        tool_input = json.loads(tool["input"]) if tool["input"] else {}
                    except json.JSONDecodeError:
                        tool_input = {}

                    tool["input"] = tool_input
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tool["id"],
                        "name": tool["name"],
                        "input": tool_input
                    })

                    self._tools_used.append({
                        "name": tool["name"],
                        "input": tool_input
                    })

                    if self.on_tool_use:
                        self.on_tool_use(tool["name"], tool_input)

                # Get final message
                final_message = stream_response.get_final_message()

            # Add assistant message to history
            self._messages.append({
                "role": "assistant",
                "content": assistant_content if assistant_content else [{"type": "text", "text": full_response}]
            })

            # Check if we need to handle tool results
            if final_message.stop_reason == "tool_use":
                tool_results = []
                for tool in tool_uses:
                    # Execute the tool
                    result = await execute_tool(tool["name"], tool["input"])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool["id"],
                        "content": result
                    })

                # Add tool results to messages
                self._messages.append({
                    "role": "user",
                    "content": tool_results
                })
            else:
                # No more tool calls, we're done
                break

        end_time = time.time()
        duration_ms = int((end_time - start_time) * 1000)

        result = InvestigationResult(
            text=full_response,
            session_id=self.session_id,
            duration_ms=duration_ms,
            num_turns=num_turns,
            tools_used=self._tools_used.copy(),
        )

        if self.on_complete:
            self.on_complete(result)

        if not stream:
            yield full_response

    async def follow_up(self, query_text: str) -> AsyncIterator[str]:
        """
        Send a follow-up query in the same session.

        Claude remembers all previous context from the investigation.

        Args:
            query_text: Follow-up query

        Yields:
            Text responses from Claude
        """
        async for chunk in self.investigate(query_text):
            yield chunk

    def reset_session(self) -> None:
        """Clear the current session to start fresh."""
        self.session_id = None
        self._tools_used = []
        self._messages = []


async def run_investigation(
    query_text: str,
    on_text: Optional[Callable[[str], None]] = None,
    on_tool_use: Optional[Callable[[str, dict], None]] = None,
) -> InvestigationResult:
    """
    Convenience function to run a one-shot investigation.

    Args:
        query_text: The investigation query
        on_text: Optional streaming text callback
        on_tool_use: Optional tool use callback

    Returns:
        InvestigationResult with full response and metadata
    """
    result_holder = []

    def capture_result(result: InvestigationResult):
        result_holder.append(result)

    agent = RobinAgent(
        on_text=on_text,
        on_tool_use=on_tool_use,
        on_complete=capture_result,
    )

    full_text = ""
    async for chunk in agent.investigate(query_text):
        full_text += chunk

    if result_holder:
        return result_holder[0]
    else:
        return InvestigationResult(text=full_text)
