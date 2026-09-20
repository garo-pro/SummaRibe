"""Layered store of AI provider configs (packaged defaults + user overrides)."""

from __future__ import annotations

from summaribe.ai.provider import AIClient
from summaribe.ai.schema import ProviderConfig
from summaribe.core.layered_store import LayeredJSONStore
from summaribe.core.paths import packaged_providers_dir, user_providers_dir


class ProviderStore(LayeredJSONStore[ProviderConfig]):
    def __init__(self) -> None:
        super().__init__(ProviderConfig, packaged_providers_dir(), user_providers_dir())

    def client_for(
        self,
        provider_id: str,
        *,
        stream: bool | None = None,
        timeout_seconds: float | None = None,
    ) -> AIClient:
        """Build a client for `provider_id`, optionally overriding its stream/timeout
        defaults (used to apply the app-level AI settings on top of a provider's own
        JSON defaults)."""
        config = self.get(provider_id)
        overrides: dict[str, object] = {}
        if stream is not None:
            overrides["stream"] = stream
        if timeout_seconds is not None:
            overrides["timeout_seconds"] = timeout_seconds
        if overrides:
            config = config.model_copy(update=overrides)
        return AIClient(config)
