try:
    from .config import OLLAMA_BASE_URL
except ImportError:
    # For direct execution by streamlit run
    from config import OLLAMA_BASE_URL
from typing import Callable, Optional
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.callbacks.base import BaseCallbackHandler


class BufferedStreamingHandler(BaseCallbackHandler):
    def __init__(self, buffer_limit: int = 60, ui_callback: Optional[Callable[[str], None]] = None, mode: str = "cli"):
        self.buffer = ""
        self.buffer_limit = buffer_limit
        self.ui_callback = ui_callback
        self.mode = mode  # 'cli' or 'ui'

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.buffer += token
        if "\n" in token or len(self.buffer) >= self.buffer_limit:
            # Only print to console in CLI mode, not in UI mode
            if self.mode == "cli":
                print(self.buffer, end="", flush=True)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""

    def on_llm_end(self, response, **kwargs) -> None:
        if self.buffer:
            # Only print to console in CLI mode, not in UI mode
            if self.mode == "cli":
                print(self.buffer, end="", flush=True)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""


# --- Configuration Data ---
# Instantiate common dependencies once
# The mode will be updated when needed, defaulting to 'cli' for backward compatibility
_common_callbacks = [BufferedStreamingHandler(buffer_limit=60, mode="cli")]

# Define common parameters for most LLMs
_common_llm_params = {
    "temperature": 0,
    "streaming": True,
    "callbacks": _common_callbacks,
}

# Map input model choices (lowercased) to their configuration
# Each config includes the class and any model-specific constructor parameters
_llm_config_map = {
    'gpt4o': {
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-4o'}
    },
    'gpt-4.1': { 
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-4.1'} 
    },
    'claude-3-5-sonnet-latest': {
        'class': ChatAnthropic,
        'constructor_params': {'model': 'claude-3-5-sonnet-latest'}
    },
    'llama3.1': { 
        'class': ChatOllama,
        'constructor_params': {'model': 'llama3.1:latest', 'base_url': OLLAMA_BASE_URL}
    },
    'gemini-2.5-flash': {
        'class': ChatGoogleGenerativeAI,
        'constructor_params': {'model': 'gemini-2.5-flash'}
    }
    # Add more models here easily:
    # 'mistral7b': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'mistral:7b', 'base_url': OLLAMA_BASE_URL}
    # },
    # 'gpt3.5': {
    #      'class': ChatOpenAI,
    #      'constructor_params': {'model_name': 'gpt-3.5-turbo', 'base_url': OLLAMA_BASE_URL}
    # }
}