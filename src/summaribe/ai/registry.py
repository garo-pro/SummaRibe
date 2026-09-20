"""Layered store of AI provider configs (packaged defaults + user overrides)."""

from __future__ import annotations

from summaribe.ai.provider import AIClient
from summaribe.ai.schema import ProviderConfig
from summaribe.core.layered_store import LayeredJSONStore
from summaribe.core.paths import packaged_providers_dir, user_providers_dir


class ProviderStore(LayeredJSONStore[ProviderConfig]):
    def __init__(self) -> None:
        super().__init__(ProviderConfig, packaged_providers_dir(), user_providers_dir())

    def client_for(self, provider_id: str) -> AIClient:
        return AIClient(self.get(provider_id))
