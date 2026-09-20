"""Pydantic schema describing an AI provider configuration file.

A provider config is plain JSON (see ``src/summaribe/data/providers/*.json``) that
tells SummaRibe how to talk to a specific chat-completion HTTP API: where it lives,
what the request body looks like, and where the reply text is found in the
response. This is what makes new providers (or self-hosted endpoints) addable by
writing JSON instead of Python.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from summaribe.core.layered_store import IdentifiedModel


class ModelsListConfig(BaseModel):
    """Optional description of how to list the models this provider has available.

    Left unset (the default) when a provider has no such endpoint, or the user
    hasn't bothered to describe one - the model list UI simply doesn't appear.
    """

    endpoint: str = Field(..., description="Path appended to base_url, e.g. '/v1/models'.")
    method: Literal["GET", "POST"] = "GET"
    request_body: dict[str, Any] | None = Field(
        default=None,
        description="JSON body template for POST-based listing; rendered like request_template.",
    )
    response_list_path: str = Field(
        default="data",
        description="Dotted path to the array of model objects in the response JSON.",
    )
    model_id_path: str = Field(
        default="id",
        description="Dotted path, within each item of that array, to the model's id/name.",
    )

    @field_validator("endpoint")
    @classmethod
    def _leading_slash(cls, value: str) -> str:
        return value if value.startswith("/") else f"/{value}"


class ProviderConfig(IdentifiedModel):
    """Full definition of a chat-completion-style HTTP provider."""

    description: str = ""

    base_url: str = Field(..., description="Scheme + host (+ optional :port), no trailing slash.")
    endpoint: str = Field(
        ..., description="Path appended to base_url, e.g. '/v1/chat/completions'."
    )
    method: Literal["POST", "GET"] = "POST"

    headers: dict[str, str] = Field(default_factory=dict)
    api_key_env: str | None = Field(
        default=None,
        description="Name of the environment variable holding the API key, if any. "
        "Exposed to templates as the 'api_key' variable.",
    )

    timeout_seconds: float = 120.0
    stream: bool = False
    stream_format: Literal["sse", "ndjson"] = "sse"

    request_template: dict[str, Any] = Field(
        ..., description="JSON payload template; string leaves may contain {{variables}}."
    )
    response_path: str = Field(
        ..., description="Dotted path to the completion text in a non-streaming JSON response."
    )
    stream_delta_path: str | None = Field(
        default=None,
        description="Dotted path to the incremental text chunk within each streamed event.",
    )
    stream_done_path: str | None = Field(
        default=None,
        description="Dotted path to a boolean flag marking the final streamed event "
        "(e.g. Ollama's 'done').",
    )

    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Default template variables (model, temperature, max_tokens, ...).",
    )

    models: ModelsListConfig | None = Field(
        default=None,
        description="How to list this provider's available models, if it has such an endpoint.",
    )

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("endpoint")
    @classmethod
    def _leading_slash(cls, value: str) -> str:
        return value if value.startswith("/") else f"/{value}"

    @property
    def url(self) -> str:
        return f"{self.base_url}{self.endpoint}"

    @property
    def models_url(self) -> str | None:
        if self.models is None:
            return None
        return f"{self.base_url}{self.models.endpoint}"
