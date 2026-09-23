"""Device selection and GPU fallback for the faster-whisper provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from summaribe.core.exceptions import TranscriptionError
from summaribe.transcription import whisper_provider
from summaribe.transcription.whisper_provider import WhisperProvider


class _FakeSegment:
    def __init__(self, text: str) -> None:
        self.start = 0.0
        self.end = 1.0
        self.text = text


class _FakeInfo:
    language = "en"


@pytest.fixture
def audio(tmp_path: Path) -> Path:
    path = tmp_path / "audio.wav"
    path.write_bytes(b"not-real-audio")
    return path


def _install_fake_model(
    monkeypatch: pytest.MonkeyPatch, provider: WhisperProvider, failing_devices: set[str]
) -> list[str]:
    """Give ``provider`` a stub model that raises on the named devices."""
    devices: list[str] = []

    class _FakeModel:
        def transcribe(self, _path: str, language: str | None = None) -> Any:
            if provider._resolved_device in failing_devices:
                raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
            return iter([_FakeSegment("hello")]), _FakeInfo()

    def _load(self: WhisperProvider) -> Any:
        devices.append(self._resolve_device())
        return _FakeModel()

    monkeypatch.setattr(WhisperProvider, "_load", _load)
    return devices


def test_auto_picks_cuda_when_the_runtime_is_usable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(whisper_provider, "_cuda_usable", lambda: True)
    assert WhisperProvider(model="tiny")._resolve_device() == "cuda"


def test_auto_falls_back_to_cpu_without_the_cuda_runtime(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(whisper_provider, "_cuda_usable", lambda: False)
    assert WhisperProvider(model="tiny")._resolve_device() == "cpu"


def test_explicit_device_is_not_second_guessed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(whisper_provider, "_cuda_usable", lambda: False)
    assert WhisperProvider(model="tiny", device="cuda")._resolve_device() == "cuda"


def test_cuda_library_error_at_runtime_retries_on_cpu(monkeypatch: pytest.MonkeyPatch, audio: Path):
    monkeypatch.setattr(whisper_provider, "_cuda_usable", lambda: True)
    provider = WhisperProvider(model="tiny")
    devices = _install_fake_model(monkeypatch, provider, failing_devices={"cuda"})
    messages: list[str] = []

    result = provider.transcribe(audio, progress_callback=messages.append)

    assert result.text == "hello"
    assert devices == ["cuda", "cpu"]
    assert any("retrying on the CPU" in message for message in messages)


def test_explicit_cuda_failure_explains_the_fix(monkeypatch: pytest.MonkeyPatch, audio: Path):
    provider = WhisperProvider(model="tiny", device="cuda")
    _install_fake_model(monkeypatch, provider, failing_devices={"cuda"})

    with pytest.raises(TranscriptionError, match="cuBLAS"):
        provider.transcribe(audio)


def test_unrelated_errors_are_not_retried(monkeypatch: pytest.MonkeyPatch, audio: Path):
    monkeypatch.setattr(whisper_provider, "_cuda_usable", lambda: False)
    provider = WhisperProvider(model="tiny")

    def _load(_self: WhisperProvider) -> Any:
        raise ValueError("broken model")

    monkeypatch.setattr(WhisperProvider, "_load", _load)
    with pytest.raises(ValueError, match="broken model"):
        provider.transcribe(audio)


def test_missing_audio_still_raises_before_loading(tmp_path: Path):
    with pytest.raises(TranscriptionError, match="Audio file not found"):
        WhisperProvider(model="tiny").transcribe(tmp_path / "missing.wav")
