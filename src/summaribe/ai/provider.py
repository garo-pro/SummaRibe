"""HTTP client that executes a ``ProviderConfig`` against a real chat-completion API."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator, Mapping
from typing import Any

import httpx

from summaribe.ai.schema import ProviderConfig
from summaribe.ai.template_engine import extract, render, try_extract
from summaribe.core.exceptions import AIProviderError, ConfigError

StreamCallback = Callable[[str], None]


def _default_messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


class AIClient:
    """Renders a provider's templates and performs the HTTP call.

    ``env`` defaults to ``os.environ`` and is only overridden in tests.
    """

    def __init__(self, config: ProviderConfig, *, env: Mapping[str, str] | None = None) -> None:
        self.config = config
        self._env = env if env is not None else os.environ

    def _resolve_api_key(self) -> str | None:
        if not self.config.api_key_env:
            return None
        value = self._env.get(self.config.api_key_env)
        if not value:
            raise ConfigError(
                f"Provider {self.config.id!r} requires environment variable "
                f"{self.config.api_key_env!r}, which is not set."
            )
        return value

    def _build_variables(self, extra: dict[str, Any]) -> dict[str, Any]:
        variables: dict[str, Any] = {**self.config.variables}
        api_key = self._resolve_api_key()
        if api_key is not None:
            variables["api_key"] = api_key
        variables["stream"] = self.config.stream
        variables.update(extra)
        return variables

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        extra_variables: dict[str, Any] | None = None,
        on_token: StreamCallback | None = None,
        client: httpx.Client | None = None,
    ) -> str:
        """Send one chat-completion request and return the full response text.

        If the provider is configured for streaming and ``on_token`` is given,
        it is invoked with each incremental chunk as it arrives.
        """
        variables = self._build_variables(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "messages": _default_messages(system_prompt, user_prompt),
                **(extra_variables or {}),
            }
        )
        payload = render(self.config.request_template, variables)
        headers = render(self.config.headers, variables) if self.config.headers else {}

        owns_client = client is None
        http_client = client or httpx.Client(timeout=self.config.timeout_seconds)
        try:
            if self.config.stream:
                return self._stream(http_client, payload, headers, on_token)
            return self._complete_once(http_client, payload, headers)
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Request to provider {self.config.id!r} failed: {exc}") from exc
        finally:
            if owns_client:
                http_client.close()

    def _complete_once(
        self, client: httpx.Client, payload: dict[str, Any], headers: dict[str, str]
    ) -> str:
        response = client.request(
            self.config.method, self.config.url, json=payload, headers=headers
        )
        response.raise_for_status()
        data = response.json()
        result = extract(data, self.config.response_path)
        return str(result)

    def _stream(
        self,
        client: httpx.Client,
        payload: dict[str, Any],
        headers: dict[str, str],
        on_token: StreamCallback | None,
    ) -> str:
        chunks: list[str] = []
        with client.stream(
            self.config.method, self.config.url, json=payload, headers=headers
        ) as response:
            response.raise_for_status()
            for event in self._iter_events(response):
                if self.config.stream_done_path and try_extract(
                    event, self.config.stream_done_path
                ):
                    break
                delta = try_extract(event, self.config.stream_delta_path)
                if delta:
                    text = str(delta)
                    chunks.append(text)
                    if on_token is not None:
                        on_token(text)
        return "".join(chunks)

    def _iter_events(self, response: httpx.Response) -> Iterator[Any]:
        if self.config.stream_format == "sse":
            yield from self._iter_sse(response)
        else:
            yield from self._iter_ndjson(response)

    @staticmethod
    def _iter_sse(response: httpx.Response) -> Iterator[Any]:
        for line in response.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                break
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                continue

    @staticmethod
    def _iter_ndjson(response: httpx.Response) -> Iterator[Any]:
        for raw_line in response.iter_lines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
