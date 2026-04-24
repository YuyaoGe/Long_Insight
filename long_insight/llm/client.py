"""Unified LLM client supporting OpenAI-compatible and Anthropic APIs."""

import json
import os
import time
from typing import Any, Dict, List, Optional

from long_insight import config


class LLMClient:
    """Unified LLM client that abstracts over OpenAI and Anthropic SDKs.

    Supports:
    - OpenAI-compatible APIs (OpenAI, DeepSeek, vLLM, etc.)
    - Anthropic native API with structured output support
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider = provider or config.LLM_PROVIDER
        self.api_key = api_key or config.API_KEY
        self.base_url = base_url or config.API_BASE_URL

        if not self.api_key:
            raise ValueError(
                "API key not set. Provide via:\n"
                "  1. OPENAI_API_KEY or ANTHROPIC_API_KEY env var\n"
                "  2. api_key parameter\n"
                "  3. .env file"
            )

        self._client = None
        self._init_client()

        # Token tracking
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.api_call_count = 0
        self.prompt_token_records: List[int] = []
        self.completion_token_records: List[int] = []

    def _init_client(self):
        if self.provider == "anthropic":
            import anthropic

            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = anthropic.Anthropic(**kwargs)
        else:
            from openai import OpenAI

            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Send a chat request and return the text response."""
        model = model or config.DEFAULT_MODEL
        temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
        max_tokens = max_tokens or config.LLM_MAX_TOKENS

        if self.provider == "anthropic":
            return self._chat_anthropic(messages, model, temperature, max_tokens, **kwargs)
        else:
            return self._chat_openai(messages, model, temperature, max_tokens, **kwargs)

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a chat request and return parsed JSON.

        If json_schema is provided and provider is Anthropic, uses structured outputs.
        Otherwise, parses JSON from the text response.
        """
        model = model or config.DEFAULT_MODEL
        temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
        max_tokens = max_tokens or config.LLM_MAX_TOKENS

        if self.provider == "anthropic" and json_schema:
            return self._chat_anthropic_structured(
                messages, json_schema, model, temperature, max_tokens, **kwargs
            )

        text = self.chat(messages, model, temperature, max_tokens, **kwargs)
        return self._parse_json(text)

    def _chat_openai(self, messages, model, temperature, max_tokens, **kwargs) -> str:
        completion = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        self._track_usage_openai(completion)
        return completion.choices[0].message.content

    def _chat_anthropic(self, messages, model, temperature, max_tokens, **kwargs) -> str:
        system_content = None
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                api_messages.append(msg)

        params = {"model": model, "messages": api_messages, "max_tokens": max_tokens, **kwargs}
        if system_content:
            params["system"] = system_content
        if temperature != 1.0:
            params["temperature"] = temperature

        response = self._client.messages.create(**params)
        self._track_usage_anthropic(response)
        return response.content[0].text

    def _chat_anthropic_structured(
        self, messages, json_schema, model, temperature, max_tokens, **kwargs
    ) -> Dict[str, Any]:
        system_content = None
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                api_messages.append(msg)

        schema = json_schema.copy()
        schema.setdefault("additionalProperties", False)

        params = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": api_messages,
            "betas": ["structured-outputs-2025-11-13"],
            "output_format": {"type": "json_schema", "schema": schema},
            **kwargs,
        }
        if system_content:
            params["system"] = system_content
        if temperature != 1.0:
            params["temperature"] = temperature

        response = self._client.beta.messages.create(**params)
        self._track_usage_anthropic(response)

        if response.stop_reason == "max_tokens":
            raise ValueError("Response truncated — increase max_tokens")

        return json.loads(response.content[0].text)

    def _track_usage_openai(self, completion):
        self.api_call_count += 1
        if hasattr(completion, "usage") and completion.usage:
            pt = completion.usage.prompt_tokens
            ct = completion.usage.completion_tokens
            self.total_prompt_tokens += pt
            self.total_completion_tokens += ct
            self.prompt_token_records.append(pt)
            self.completion_token_records.append(ct)

    def _track_usage_anthropic(self, response):
        self.api_call_count += 1
        if hasattr(response, "usage") and response.usage:
            pt = getattr(response.usage, "input_tokens", 0)
            ct = getattr(response.usage, "output_tokens", 0)
            self.total_prompt_tokens += pt
            self.total_completion_tokens += ct
            self.prompt_token_records.append(pt)
            self.completion_token_records.append(ct)

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """Extract JSON from an LLM text response."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Failed to parse JSON from response: {text[:200]}")

    def chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Chat with automatic retry on failure."""
        max_retries = max_retries or config.LLM_MAX_RETRIES
        retry_delay = retry_delay or config.LLM_RETRY_DELAY

        for attempt in range(max_retries):
            try:
                return self.chat(messages, model, temperature, max_tokens, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise RuntimeError(f"LLM call failed after {max_retries} retries: {e}") from e

    def get_token_stats(self) -> Dict[str, Any]:
        """Return token usage statistics."""
        if self.api_call_count == 0:
            return {"api_calls": 0, "total_tokens": 0}

        return {
            "api_calls": self.api_call_count,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "avg_prompt_tokens": self.total_prompt_tokens / self.api_call_count,
            "avg_completion_tokens": self.total_completion_tokens / self.api_call_count,
            "max_prompt_tokens": max(self.prompt_token_records) if self.prompt_token_records else 0,
            "max_completion_tokens": (
                max(self.completion_token_records) if self.completion_token_records else 0
            ),
        }
