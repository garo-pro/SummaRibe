"""Persistent application settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from summaribe.core.paths import default_work_dir, settings_file

OutputFormat = Literal["txt", "srt", "vtt", "json"]


def _default_output_formats() -> list[OutputFormat]:
    return ["txt"]


class TranscriptionSettings(BaseModel):
    default_provider: str = "whisper"
    model: str = "small"
    model_path: str | None = None
    device: str = "auto"
    compute_type: str = "default"
    language: str | None = None  # None = auto-detect


class AISettings(BaseModel):
    improve_provider_id: str = "ollama"
    improve_prompt_id: str = "improve_default"
    improve_model: str | None = None  # None = use the provider's own default `variables.model`
    summarize_provider_id: str = "ollama"
    summarize_prompt_id: str = "summarize_default"
    summarize_model: str | None = None
    streaming: bool = False  # matches the shipped providers' own `stream: false` default
    timeout_seconds: float = 120.0
    temperature: float = 0.3
    max_tokens: int = 2048


class DictionarySettings(BaseModel):
    enabled: bool = False
    active_dictionary_ids: list[str] = Field(default_factory=list)


class GUISettings(BaseModel):
    theme: Literal["system", "light", "dark"] = "system"
    auto_open_output_folder: bool = False
    window_width: int = 1100
    window_height: int = 750


class AppSettings(BaseModel):
    work_dir: str = Field(default_factory=lambda: str(default_work_dir()))
    audio_format: Literal["mp3", "wav", "flac", "m4a"] = "mp3"
    audio_quality_kbps: int = 192
    keep_intermediate_files: bool = True
    output_formats: list[OutputFormat] = Field(default_factory=_default_output_formats)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    transcription: TranscriptionSettings = Field(default_factory=TranscriptionSettings)
    ai: AISettings = Field(default_factory=AISettings)
    dictionary: DictionarySettings = Field(default_factory=DictionarySettings)
    gui: GUISettings = Field(default_factory=GUISettings)


class SettingsManager:
    """Loads settings from disk on construction; call ``save`` to persist edits."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_file()
        self.settings = self.load()

    def load(self) -> AppSettings:
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return AppSettings.model_validate(data)
        return AppSettings()

    def save(self, settings: AppSettings | None = None) -> None:
        if settings is not None:
            self.settings = settings
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.settings.model_dump_json(indent=2), encoding="utf-8")
