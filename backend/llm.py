"""Shared LLM client utilities for Argus backend."""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

log = logging.getLogger("argus")

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def get_llm_client():
    """Creates LLM client based on ARGUS_LLM_* environment variables."""
    provider = os.environ.get("ARGUS_LLM_PROVIDER", "anthropic")
    api_key = os.environ.get("ARGUS_LLM_API_KEY")
    base_url = os.environ.get("ARGUS_LLM_BASE_URL")
    model = os.environ.get("ARGUS_LLM_MODEL", DEFAULT_MODEL)

    if not api_key:
        raise RuntimeError(
            "ARGUS_LLM_API_KEY nicht gesetzt. Bitte als Umgebungsvariable konfigurieren."
        )

    if provider == "anthropic":
        from anthropic import Anthropic
        return "anthropic", Anthropic(api_key=api_key), model
    elif provider == "azure":
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=base_url,
            api_version=os.environ.get("ARGUS_LLM_API_VERSION", "2024-12-01-preview"),
        )
        return "openai", client, model
    else:
        from openai import OpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return "openai", OpenAI(**kwargs), model


def call_llm(system_prompt: str, messages: list[dict]) -> str:
    """Calls the configured LLM with a system prompt and message history.

    Args:
        system_prompt: The system prompt string.
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts.

    Returns:
        The assistant's response text.
    """
    provider_type, client, model = get_llm_client()
    log.info("LLM-Aufruf: provider=%s, model=%s", provider_type, model)

    if provider_type == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
    else:
        openai_messages = [{"role": "system", "content": system_prompt}] + messages
        response = client.chat.completions.create(
            model=model,
            max_tokens=2048,
            messages=openai_messages,
        )
        return response.choices[0].message.content
