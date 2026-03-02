"""Shared LLM client utilities for Argus backend."""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

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


def stream_llm(system_prompt: str, messages: list[dict], max_tokens: int = 2048):
    """Generator that yields text chunks from the configured LLM.

    Args:
        system_prompt: The system prompt string.
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
        max_tokens: Maximum number of tokens to generate.

    Yields:
        Text chunks as they arrive from the LLM.
    """
    provider_type, client, model = get_llm_client()
    log.info("LLM-Stream: provider=%s, model=%s, max_tokens=%d", provider_type, model, max_tokens)

    if provider_type == "anthropic":
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
    else:
        openai_messages = [{"role": "system", "content": system_prompt}] + messages
        stream = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=openai_messages,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content


def call_llm(system_prompt: str, messages: list[dict], max_tokens: int = 2048) -> str:
    """Calls the configured LLM with a system prompt and message history.

    Args:
        system_prompt: The system prompt string.
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
        max_tokens: Maximum number of tokens to generate.

    Returns:
        The assistant's response text.
    """
    provider_type, client, model = get_llm_client()
    log.info("LLM-Aufruf: provider=%s, model=%s, max_tokens=%d", provider_type, model, max_tokens)

    if provider_type == "anthropic":
        # Use streaming to avoid 10-minute timeout on long requests
        collected = []
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                collected.append(text)
        response = stream.get_final_message()
        stop = response.stop_reason
        usage = response.usage
        log.info(
            "LLM-Antwort: stop_reason=%s, input_tokens=%d, output_tokens=%d",
            stop, usage.input_tokens, usage.output_tokens,
        )
        if stop == "max_tokens":
            log.warning("LLM-Output wurde bei max_tokens=%d abgeschnitten!", max_tokens)
        return "".join(collected)
    else:
        openai_messages = [{"role": "system", "content": system_prompt}] + messages
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=openai_messages,
        )
        finish = response.choices[0].finish_reason
        usage = response.usage
        log.info(
            "LLM-Antwort: finish_reason=%s, prompt_tokens=%d, completion_tokens=%d",
            finish, usage.prompt_tokens, usage.completion_tokens,
        )
        if finish == "length":
            log.warning("LLM-Output wurde bei max_tokens=%d abgeschnitten!", max_tokens)
        return response.choices[0].message.content
