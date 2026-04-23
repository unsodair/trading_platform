"""
LLM factory — returns the active adapter based on configuration.
"""

from __future__ import annotations

from app.config import ActiveLLM, settings
from app.llms.base import BaseLLM


def get_llm_adapter() -> BaseLLM:
    """Instantiate and return the configured LLM adapter."""
    match settings.active_llm:
        case ActiveLLM.OPENAI:
            from app.llms.openai_adapter import OpenAIAdapter
            return OpenAIAdapter()
        case ActiveLLM.ANTHROPIC:
            from app.llms.anthropic_adapter import AnthropicAdapter
            return AnthropicAdapter()
        case ActiveLLM.GEMINI:
            from app.llms.gemini_adapter import GeminiAdapter
            return GeminiAdapter()
        case ActiveLLM.OLLAMA:
            from app.llms.ollama_adapter import OllamaAdapter
            return OllamaAdapter()
        case _:
            from app.llms.openai_adapter import OpenAIAdapter
            return OpenAIAdapter()
