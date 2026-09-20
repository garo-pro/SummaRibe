"""Common interface every transcription provider implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

ProgressCallback = Callable[[str], None]


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptionResult(BaseModel):
    text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)
    language: str | None = None


class TranscriptionProvider(ABC):
    """Base class for a speech-to-text engine.

    Subclasses should import their heavy ML dependency lazily (inside
    ``transcribe``/``is_available``, not at module import time) so the rest of
    SummaRibe works without every ASR backend installed.
    """

    id: ClassVar[str]
    display_name: ClassVar[str]

    def __init__(self, **config: object) -> None:
        self.config = config

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider's dependencies are importable."""

    @abstractmethod
    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> TranscriptionResult: ...
