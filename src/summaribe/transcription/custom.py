"""Custom local models: reuse an existing architecture's loader with a browsed path.

Every built-in provider already accepts a ``model_path`` override, since a
"custom model" is just a checkpoint sharing a supported architecture (Whisper,
Parakeet/NeMo, or a Transformers speech-seq2seq model). This module is the
single place the GUI and CLI go through so "custom model" stays a thin wrapper
instead of a fourth parallel implementation.
"""

from __future__ import annotations

from pathlib import Path

from summaribe.core.exceptions import RegistryError
from summaribe.transcription.base import TranscriptionProvider
from summaribe.transcription.registry import create_provider

#: architecture id -> underlying registered provider id
SUPPORTED_ARCHITECTURES: dict[str, str] = {
    "whisper": "whisper",
    "parakeet": "parakeet",
    "qwen3_asr": "qwen3_asr",
}


def create_custom_provider(
    architecture: str, model_path: Path, **extra_config: object
) -> TranscriptionProvider:
    if architecture not in SUPPORTED_ARCHITECTURES:
        raise RegistryError(
            f"Unsupported custom model architecture {architecture!r}. "
            f"Choose one of: {', '.join(SUPPORTED_ARCHITECTURES)}"
        )
    provider_id = SUPPORTED_ARCHITECTURES[architecture]
    return create_provider(provider_id, model_path=str(model_path), **extra_config)
