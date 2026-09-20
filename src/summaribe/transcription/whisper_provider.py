"""Whisper transcription via faster-whisper (CTranslate2).

Accepts either a standard Whisper model size (``tiny``, ``base``, ``small``,
``medium``, ``large-v3``, ...) or a filesystem path to a CTranslate2-converted
custom Whisper checkpoint, which is how "browse for a custom model" works for
this architecture family.
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
class WhisperProvider(TranscriptionProvider):
    id = "whisper"
    display_name = "Whisper (faster-whisper)"

    def __init__(
        self,
        *,
        model: str = "small",
        model_path: str | None = None,
        device: str = "auto",
        compute_type: str = "default",
        **config: Any,
    ) -> None:
        super().__init__(
            model=model, model_path=model_path, device=device, compute_type=compute_type, **config
        )
        self.model_name_or_path = model_path or model
        self.device = device
        self.compute_type = compute_type
        self._model: Any = None

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return False
        return True

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ProviderUnavailableError(
                "faster-whisper is not installed. Install the 'whisper' extra: "
                "uv sync --extra whisper"
            ) from exc
        try:
            self._model = WhisperModel(
                self.model_name_or_path, device=self.device, compute_type=self.compute_type
            )
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to load Whisper model {self.model_name_or_path!r}: {exc}"
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
        segments_iter, info = model.transcribe(str(audio_path), language=language)
        segments: list[TranscriptSegment] = []
        text_parts: list[str] = []
        for segment in segments_iter:
            segments.append(
                TranscriptSegment(start=segment.start, end=segment.end, text=segment.text)
            )
            text_parts.append(segment.text)
            if progress_callback is not None:
                progress_callback(f"[{segment.start:.1f}s] {segment.text.strip()}")
        return TranscriptionResult(
            text="".join(text_parts).strip(),
            segments=segments,
            language=getattr(info, "language", language),
        )
