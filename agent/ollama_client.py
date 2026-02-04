"""Ollama client wrapper that provides Anthropic-compatible interface."""
import asyncio
import json
import requests
from typing import Any, AsyncIterator, Optional
from dataclasses import dataclass

from config import OLLAMA_BASE_URL


@dataclass
class OllamaMessage:
    """Message format compatible with Anthropic API."""
    role: str
    content: str


class OllamaClient:
    """
    Wrapper for Ollama API that provides an interface compatible with Anthropic SDK.
    
    This allows using local Ollama models with the same agent architecture.
    """
    
    def __init__(self, model: str, base_url: Optional[str] = None):
        """
        Initialize Ollama client.
        
        Args:
            model: Ollama model name (e.g., 'llama3.1', 'mistral')
            base_url: Ollama server URL (default from config)
        """
        self.model = model
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self._validate_connection()
    
    def _validate_connection(self):
        """Check if Ollama server is reachable."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            
            # Check if requested model exists
            if not any(self.model in name for name in model_names):
                print(f"Warning: Model '{self.model}' not found in Ollama. Available models: {model_names}")
        except requests.RequestException as e:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Make sure Ollama is running. Error: {e}"
            )
    
    async def _stream_chat(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] = None,
    ) -> AsyncIterator[dict]:
        """
        Stream chat responses from Ollama.
        
        Args:
            messages: List of message dicts with role and content
            system: System prompt
            tools: Tool definitions (for function calling - limited support)
            
        Yields:
            Response chunks in Anthropic-compatible format
        """
        # Convert to Ollama format
        ollama_messages = []
        
        if system:
            ollama_messages.append({"role": "system", "content": system})
        
        for msg in messages:
            ollama_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        # Prepare request
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": True,
        }
        
        # Add tools context to system message if provided
        if tools:
            tools_desc = self._format_tools_for_ollama(tools)
            if ollama_messages and ollama_messages[0]["role"] == "system":
                ollama_messages[0]["content"] += f"\n\nAvailable tools:\n{tools_desc}"
            else:
                ollama_messages.insert(0, {
                    "role": "system",
                    "content": f"Available tools:\n{tools_desc}"
                })
        
        # Stream response
        try:
            response = requests.post(url, json=payload, stream=True, timeout=300)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if chunk.get("done"):
                            break
                        
                        # Convert to Anthropic-compatible format
                        if "message" in chunk:
                            content = chunk["message"].get("content", "")
                            if content:
                                yield {
                                    "type": "content_block_delta",
                                    "delta": {"type": "text_delta", "text": content}
                                }
                    except json.JSONDecodeError:
                        continue
                        
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama API error: {e}")
    
    def _format_tools_for_ollama(self, tools: list[dict]) -> str:
        """
        Format tool definitions for Ollama (which doesn't have native function calling).
        
        We provide tools as text descriptions that the model can reference.
        """
        formatted = []
        for tool in tools:
            name = tool.get("name", "")
            description = tool.get("description", "")
            formatted.append(f"- {name}: {description}")
        return "\n".join(formatted)
    
    async def _parse_tool_calls_from_text(self, text: str) -> list[dict]:
        """
        Parse tool calls from model output.
        
        Since Ollama doesn't have native function calling, we look for specific patterns
        in the text output.
        """
        tool_calls = []
        
        # Look for tool call patterns like: [TOOL: darkweb_search] {"query": "..."}
        import re
        pattern = r'\[TOOL:\s*(\w+)\]\s*(\{[^}]+\})'
        matches = re.finditer(pattern, text, re.MULTILINE)
        
        for match in matches:
            tool_name = match.group(1)
            try:
                tool_input = json.loads(match.group(2))
                tool_calls.append({
                    "type": "tool_use",
                    "id": f"toolu_{len(tool_calls)}",
                    "name": tool_name,
                    "input": tool_input
                })
            except json.JSONDecodeError:
                continue
        
        return tool_calls
    
    def messages_create(
        self,
        model: str,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 4096,
        tools: list[dict] = None,
        **kwargs
    ) -> Any:
        """
        Synchronous message creation (for compatibility).
        
        Note: This is a simplified version. The async stream method is preferred.
        """
        # Run async method synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        full_response = ""
        try:
            async def collect():
                nonlocal full_response
                async for chunk in self._stream_chat(messages, system, tools):
                    if chunk.get("type") == "content_block_delta":
                        full_response += chunk["delta"]["text"]
            
            loop.run_until_complete(collect())
        finally:
            loop.close()
        
        # Return in Anthropic-compatible format
        return type('Response', (), {
            'content': [{"type": "text", "text": full_response}],
            'stop_reason': 'end_turn',
            'usage': {'input_tokens': 0, 'output_tokens': 0}
        })()


def is_ollama_model(model: str) -> bool:
    """
    Determine if a model name refers to an Ollama model.
    
    Args:
        model: Model name
        
    Returns:
        True if it's an Ollama model, False if it's a Claude model
    """
    claude_prefixes = ["claude-", "claude_"]
    return not any(model.lower().startswith(prefix) for prefix in claude_prefixes)


def get_available_ollama_models() -> list[str]:
    """
    Fetch list of available Ollama models from the server.
    
    Returns:
        List of model names
    """
    try:
        response = requests.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=5)
        response.raise_for_status()
        models = response.json().get("models", [])
        return [m.get("name", "") for m in models if m.get("name")]
    except requests.RequestException:
        return []
