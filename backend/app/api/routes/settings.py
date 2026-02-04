"""Settings endpoints."""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
import os
import sys

# Add parent directory to path to import agent modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

try:
    from agent.ollama_client import get_available_ollama_models, is_ollama_model
    from config import DEFAULT_MODEL, ANTHROPIC_API_KEY, OLLAMA_BASE_URL
except ImportError:
    # Fallback if imports fail
    def get_available_ollama_models():
        return []
    def is_ollama_model(model):
        return not model.startswith("claude-")
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    ANTHROPIC_API_KEY = None
    OLLAMA_BASE_URL = "http://127.0.0.1:11434"

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/models")
async def get_models():
    """
    Get information about available AI models and their connection status.
    
    Returns:
        - current_model: The currently configured default model
        - claude_available: Whether Claude (Anthropic) is available
        - ollama_available: Whether Ollama is available
        - ollama_models: List of available Ollama models
        - claude_models: List of common Claude models
    """
    # Check if Anthropic API key is configured
    claude_available = bool(ANTHROPIC_API_KEY and ANTHROPIC_API_KEY.strip())
    
    # Try to get Ollama models
    ollama_models = []
    ollama_available = False
    try:
        ollama_models = get_available_ollama_models()
        ollama_available = len(ollama_models) > 0
    except Exception:
        ollama_available = False
    
    # List of common Claude models
    claude_models = [
        "claude-sonnet-4-20250514",
        "claude-sonnet-4-5-20250514",
        "claude-opus-4-20250514",
        "claude-opus-4-5-20250514",
    ]
    
    # Determine which provider the current model uses
    current_model = DEFAULT_MODEL
    current_model_type = "ollama" if is_ollama_model(current_model) else "claude"
    
    return {
        "current_model": current_model,
        "current_model_type": current_model_type,
        "claude": {
            "available": claude_available,
            "models": claude_models if claude_available else [],
            "configured": claude_available,
        },
        "ollama": {
            "available": ollama_available,
            "models": ollama_models,
            "base_url": OLLAMA_BASE_URL,
            "configured": ollama_available,
        },
    }
