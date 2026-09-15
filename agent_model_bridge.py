"""Bridges Chatterbase's LLM profile registry (llm_registry.py) to a
LangChain BaseChatModel, so agent_orchestrator.py's deepagents graph uses
whichever profile is currently active - the same profile /api/chat uses via
llm_providers.py, just constructed for LangChain instead of Chatterbase's own
provider classes. llm_providers.py and /api/chat are untouched by this.
"""
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

import llm_registry

# local_llm/lm_studio/nvidia_nim all speak the OpenAI-compatible chat
# completions API - only the base_url differs, matching llm_providers.py's
# existing treatment of these three as one code path.
_OPENAI_COMPATIBLE_TYPES = ("local_llm", "nvidia_nim", "lm_studio")


def get_chat_model():
    """Return a BaseChatModel for the active LLM profile."""
    profile = llm_registry.get_active_profile()
    if profile is None:
        raise ValueError("No LLM profile configured - add one in LLM Settings first")

    provider_type = profile["provider_type"]
    if provider_type in _OPENAI_COMPATIBLE_TYPES:
        return ChatOpenAI(base_url=profile["url"], api_key="not-needed", model=profile["model"])
    if provider_type == "openai":
        return ChatOpenAI(api_key=profile["api_key"], model=profile["model"])
    if provider_type == "gemini":
        return ChatGoogleGenerativeAI(google_api_key=profile["api_key"], model=profile["model"])

    raise ValueError(f"Unknown provider_type: {provider_type}")
