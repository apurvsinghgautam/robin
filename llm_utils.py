from config import OLLAMA_BASE_URL
from typing import Callable, Optional
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.callbacks.base import BaseCallbackHandler


class BufferedStreamingHandler(BaseCallbackHandler):
    def __init__(self, buffer_limit: int = 60, ui_callback: Optional[Callable[[str], None]] = None):
        self.buffer = ""
        self.buffer_limit = buffer_limit
        self.ui_callback = ui_callback

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.buffer += token
        if "\n" in token or len(self.buffer) >= self.buffer_limit:
            print(self.buffer, end="", flush=True)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""

    def on_llm_end(self, response, **kwargs) -> None:
        if self.buffer:
            print(self.buffer, end="", flush=True)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""


# --- Configuration Data ---
# Instantiate common dependencies once
_common_callbacks = [BufferedStreamingHandler(buffer_limit=60)]

# Define common parameters for most LLMs
_common_llm_params = {
    "temperature": 0,
    "streaming": True,
    "callbacks": _common_callbacks,
}

# Map input model choices (lowercased) to their configuration
# Each config includes the class and any model-specific constructor parameters
_llm_config_map = {
    'gpt-4.1': { 
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-4.1'} 
    },
    'gpt-5.1': { 
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-5.1'} 
    },
    'gpt-5-mini': { 
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-5-mini'} 
    },
    'gpt-5-nano': { 
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-5-nano'} 
    },
    'claude-sonnet-4-5': {
        'class': ChatAnthropic,
        'constructor_params': {'model': 'claude-sonnet-4-5'}
    },
    'claude-sonnet-4-0': {
        'class': ChatAnthropic,
        'constructor_params': {'model': 'claude-sonnet-4-0'}
    },
    'gemini-2.5-flash': {
        'class': ChatGoogleGenerativeAI,
        'constructor_params': {'model': 'gemini-2.5-flash'}
    },
    'gemini-2.5-flash-lite': {
        'class': ChatGoogleGenerativeAI,
        'constructor_params': {'model': 'gemini-2.5-flash-lite'}
    },
    'gemini-2.5-pro': {
        'class': ChatGoogleGenerativeAI,
        'constructor_params': {'model': 'gemini-2.5-pro'}
    },
    'llama3.2': { 
        'class': ChatOllama,
        'constructor_params': {'model': 'llama3.2:latest', 'base_url': OLLAMA_BASE_URL}
    },
    'llama3.1': { 
        'class': ChatOllama,
        'constructor_params': {'model': 'llama3.1:latest', 'base_url': OLLAMA_BASE_URL}
    },
    'gemma3': { 
        'class': ChatOllama,
        'constructor_params': {'model': 'gemma3:latest', 'base_url': OLLAMA_BASE_URL}
    },
    'deepseek-r1': { 
        'class': ChatOllama,
        'constructor_params': {'model': 'deepseek-r1:latest', 'base_url': OLLAMA_BASE_URL}
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