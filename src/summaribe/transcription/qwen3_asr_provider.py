"""Qwen3-ASR transcription via Hugging Face Transformers.

Accepts a Hugging Face hub id (e.g. ``Qwen/Qwen3-ASR``) or a local model
directory, which is how "browse for a custom model" works for this
architecture family.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from summaribe.core.exceptions import ModelLoadError, ProviderUnavailableError, TranscriptionError
from summaribe.transcription.base import (
    ProgressCallback,
    TranscriptionProvider,
    TranscriptionResult,
)
from summaribe.transcription.registry import register


@register
class Qwen3ASRProvider(TranscriptionProvider):
    id = "qwen3_asr"
    display_name = "Qwen3-ASR (Transformers)"

    def __init__(
        self,
        *,
        model: str = "Qwen/Qwen3-ASR",
        model_path: str | None = None,
        device: str = "auto",
        **config: Any,
    ) -> None:
        super().__init__(model=model, model_path=model_path, device=device, **config)
        self.model_name_or_path = model_path or model
        self.device = device
        self._model: Any = None
        self._processor: Any = None

    def is_available(self) -> bool:
        try:
            import transformers  # noqa: F401
        except ImportError:
            return False
        return True

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
        except ImportError as exc:
            raise ProviderUnavailableError(
                "transformers/torch are not installed. Install the 'qwen' extra: "
                "uv sync --extra qwen"
            ) from exc
        try:
            self._processor = AutoProcessor.from_pretrained(self.model_name_or_path)
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(self.model_name_or_path)
            if self.device != "auto":
                self._model = self._model.to(self.device)
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to load Qwen3-ASR model {self.model_name_or_path!r}: {exc}"
            ) from exc

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> TranscriptionResult:
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")
        self._load()
        if progress_callback is not None:
            progress_callback("Running Qwen3-ASR inference...")
        try:
            import soundfile as sf

            audio, sample_rate = sf.read(str(audio_path))
            inputs = self._processor(
                audio, sampling_rate=sample_rate, return_tensors="pt", language=language
            )
            generated_ids = self._model.generate(**inputs)
            text = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        except Exception as exc:
            raise TranscriptionError(f"Qwen3-ASR transcription failed: {exc}") from exc
        return TranscriptionResult(text=text.strip(), segments=[], language=language)
