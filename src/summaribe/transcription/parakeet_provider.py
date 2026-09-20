"""NVIDIA Parakeet-TDT transcription via NeMo.

Accepts either a pretrained model name known to NeMo (e.g.
``nvidia/parakeet-tdt-1.1b``) or a local ``.nemo`` checkpoint path, which is
how "browse for a custom model" works for this architecture family.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from summaribe.core.exceptions import ModelLoadError, ProviderUnavailableError, TranscriptionError
from summaribe.transcription.base import (
    ProgressCallback,
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptSegment,
)
from summaribe.transcription.registry import register


@register
class ParakeetProvider(TranscriptionProvider):
    id = "parakeet"
    display_name = "Parakeet-TDT (NeMo)"

    def __init__(
        self,
        *,
        model: str = "nvidia/parakeet-tdt-1.1b",
        model_path: str | None = None,
        **config: Any,
    ) -> None:
        super().__init__(model=model, model_path=model_path, **config)
        self.model_name_or_path = model_path or model
        self._model: Any = None

    def is_available(self) -> bool:
        try:
            import nemo.collections.asr  # noqa: F401
        except ImportError:
            return False
        return True

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            import nemo.collections.asr as nemo_asr
        except ImportError as exc:
            raise ProviderUnavailableError(
                "nemo_toolkit[asr] is not installed. Install the 'parakeet' extra: "
                "uv sync --extra parakeet"
            ) from exc
        try:
            if self.model_name_or_path.endswith(".nemo"):
                self._model = nemo_asr.models.ASRModel.restore_from(self.model_name_or_path)
            else:
                self._model = nemo_asr.models.ASRModel.from_pretrained(self.model_name_or_path)
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to load Parakeet model {self.model_name_or_path!r}: {exc}"
            ) from exc
        return self._model

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> TranscriptionResult:
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")
        model = self._load()
        if progress_callback is not None:
            progress_callback("Running Parakeet-TDT inference...")
        try:
            output = model.transcribe([str(audio_path)])
        except Exception as exc:
            raise TranscriptionError(f"Parakeet transcription failed: {exc}") from exc
        text = output[0].text if hasattr(output[0], "text") else str(output[0])
        segments: list[TranscriptSegment] = []
        timestamps = getattr(output[0], "timestamp", None)
        if timestamps and "segment" in timestamps:
            for seg in timestamps["segment"]:
                segments.append(
                    TranscriptSegment(start=seg["start"], end=seg["end"], text=seg["segment"])
                )
        return TranscriptionResult(text=text.strip(), segments=segments, language=language)
