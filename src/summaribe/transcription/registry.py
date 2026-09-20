"""Registry mapping provider ids to `TranscriptionProvider` classes.

Built-in providers register themselves via ``@register`` at import time.
Importing this module does not import the heavy ML backends themselves - each
provider module only imports its ML dependency lazily inside its methods.
"""

from __future__ import annotations

from summaribe.core.exceptions import RegistryError
from summaribe.transcription.base import TranscriptionProvider

_REGISTRY: dict[str, type[TranscriptionProvider]] = {}


def register(cls: type[TranscriptionProvider]) -> type[TranscriptionProvider]:
    _REGISTRY[cls.id] = cls
    return cls


def get_provider_class(provider_id: str) -> type[TranscriptionProvider]:
    try:
        return _REGISTRY[provider_id]
    except KeyError as exc:
        raise RegistryError(f"No transcription provider registered as {provider_id!r}") from exc


def create_provider(provider_id: str, **config: object) -> TranscriptionProvider:
    return get_provider_class(provider_id)(**config)


def list_provider_classes() -> list[type[TranscriptionProvider]]:
    return list(_REGISTRY.values())


def _ensure_builtins_loaded() -> None:
    # Imported for side effects (each module calls @register on its class).
    from summaribe.transcription import (  # noqa: F401
        parakeet_provider,
        qwen3_asr_provider,
        whisper_provider,
    )


_ensure_builtins_loaded()
