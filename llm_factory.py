"""
llm_factory.py
--------------
Shared LLM factory for the Resumatic multi-agent pipeline.

All LLM-powered agents (Orchestrator, Enhancer) call get_llm() from this
module. It builds a LangChain ChatOpenAI instance pointed at the OpenRouter
API endpoint, using per-agent model configuration from environment variables.

OpenRouter is OpenAI-API-compatible, so no extra SDK is needed — we simply
point langchain-openai at https://openrouter.ai/api/v1 with the OpenRouter
API key.

Environment variables (set in .env):
  OPENROUTER_API_KEY          — Your OpenRouter API key (required)
  ORCHESTRATOR_MODEL          — Model slug for Agent 1 (Orchestrator)
  ENHANCER_MODEL              — Model slug for Agent 3 (Enhancer)
  OPENROUTER_SITE_URL         — Optional: your site URL (sent as HTTP-Referer)
  OPENROUTER_SITE_NAME        — Optional: your app name (sent as X-Title)

See https://openrouter.ai/models for the full list of available model slugs.
"""

import os
from langchain_openai import ChatOpenAI

# OpenRouter's OpenAI-compatible API base URL
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Default model fallbacks (used when env vars are not set)
DEFAULT_ORCHESTRATOR_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
DEFAULT_ENHANCER_MODEL     = "anthropic/claude-3.5-haiku"


def get_llm(agent: str, temperature: float = 0.0) -> ChatOpenAI:
    """
    Build and return a LangChain ChatOpenAI instance configured for OpenRouter.

    Args:
        agent:       One of "orchestrator" or "enhancer". Used to look up
                     the per-agent model env var.
        temperature: Sampling temperature for the LLM (default 0 = deterministic).

    Returns:
        A configured ChatOpenAI instance pointing at OpenRouter.

    Raises:
        EnvironmentError: If OPENROUTER_API_KEY is not set or is invalid.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY is not set. "
            "Please add it to your .env file. "
            "Get your key at https://openrouter.ai/keys"
        )

    # Resolve per-agent model
    model_name = _resolve_model(agent)

    # Optional headers recommended by OpenRouter for leaderboard visibility
    site_url  = os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000")
    site_name = os.getenv("OPENROUTER_SITE_NAME", "Resumatic")

    llm = ChatOpenAI(
        model=model_name,
        temperature=temperature,
        openai_api_key=api_key,
        openai_api_base=OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": site_url,
            "X-Title": site_name,
        },
    )

    print(f"[LLM Factory] Agent '{agent}' → model: {model_name}")
    return llm


def _resolve_model(agent: str) -> str:
    """
    Return the model slug for the given agent, reading from env vars.

    Env var mapping:
      orchestrator → ORCHESTRATOR_MODEL
      enhancer     → ENHANCER_MODEL
    """
    env_map = {
        "orchestrator": ("ORCHESTRATOR_MODEL", DEFAULT_ORCHESTRATOR_MODEL),
        "enhancer":     ("ENHANCER_MODEL",     DEFAULT_ENHANCER_MODEL),
    }

    if agent not in env_map:
        raise ValueError(
            f"Unknown agent '{agent}'. Valid values: {list(env_map.keys())}"
        )

    env_var, default = env_map[agent]
    return os.getenv(env_var, default)
