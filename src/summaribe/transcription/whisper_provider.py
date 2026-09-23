"""Whisper transcription via faster-whisper (CTranslate2).

Accepts either a standard Whisper model size (``tiny``, ``base``, ``small``,
``medium``, ``large-v3``, ...) or a filesystem path to a CTranslate2-converted
custom Whisper checkpoint, which is how "browse for a custom model" works for
this architecture family.

CTranslate2 loads the CUDA libraries lazily, so a machine with an NVIDIA driver
but no cuBLAS/cuDNN runtime only fails part-way through the first transcription.
The device handling below probes for those libraries up front and falls back to
CPU rather than letting that surface as a mid-pipeline crash.
"""

from __future__ import annotations

import os
import sys
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

# CTranslate2 4.x needs cuBLAS 12 and cuDNN 9 on top of the driver.
_CUDA_LIBRARIES = {
    "nt": ("cublas64_12.dll", "cudnn64_9.dll"),
    "posix": ("libcublas.so.12", "libcudnn.so.9"),
}

_CUDA_HELP = (
    "The NVIDIA driver is present but the CUDA runtime libraries (cuBLAS 12 and "
    "cuDNN 9) are not. Install them with 'uv pip install nvidia-cublas-cu12 "
    "nvidia-cudnn-cu12', or set the transcription device to 'cpu' in Settings."
)


def _add_nvidia_dll_directories() -> None:
    """Make pip-installed CUDA libraries findable on Windows.

    The ``nvidia-*-cu12`` wheels drop their DLLs in ``site-packages/nvidia/*/bin``,
    which is not on the DLL search path, so CTranslate2 cannot see them without
    this. No-op everywhere else.
    """
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return
    for entry in sys.path:
        nvidia_root = Path(entry) / "nvidia"
        if not nvidia_root.is_dir():
            continue
        for bin_dir in nvidia_root.glob("*/bin"):
            try:
                os.add_dll_directory(str(bin_dir))
            except OSError:  # pragma: no cover - path vanished between glob and use
                continue


def _cuda_libraries_loadable() -> bool:
    import ctypes

    names = _CUDA_LIBRARIES.get(os.name)
    if not names:
        return True
    loader = getattr(ctypes, "WinDLL", ctypes.CDLL)
    for name in names:
        try:
            loader(name)
        except OSError:
            return False
    return True


def _cuda_usable() -> bool:
    _add_nvidia_dll_directories()
    try:
        import ctranslate2
    except ImportError:
        return False
    try:
        if ctranslate2.get_cuda_device_count() <= 0:
            return False
    except Exception:
        return False
    return _cuda_libraries_loadable()


def _is_cuda_library_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "cublas" in message or "cudnn" in message or "cuda" in message


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
        self._resolved_device: str | None = None

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return False
        return True

    def _resolve_device(self) -> str:
        """Turn ``auto`` into a device CTranslate2 can actually run on."""
        if self._resolved_device is not None:
            return self._resolved_device
        if self.device == "auto":
            self._resolved_device = "cuda" if _cuda_usable() else "cpu"
        else:
            if self.device.startswith("cuda"):
                _add_nvidia_dll_directories()
            self._resolved_device = self.device
        return self._resolved_device

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
        device = self._resolve_device()
        try:
            self._model = WhisperModel(
                self.model_name_or_path, device=device, compute_type=self.compute_type
            )
        except Exception as exc:
            detail = f" {_CUDA_HELP}" if _is_cuda_library_error(exc) else ""
            raise ModelLoadError(
                f"Failed to load Whisper model {self.model_name_or_path!r} on {device}: "
                f"{exc}.{detail}"
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
        try:
            return self._transcribe_once(
                audio_path, language=language, progress_callback=progress_callback
            )
        except Exception as exc:
            if not _is_cuda_library_error(exc) or self._resolved_device == "cpu":
                raise
            if self.device != "auto":
                raise TranscriptionError(
                    f"Whisper transcription on {self._resolved_device} failed: {exc}. {_CUDA_HELP}"
                ) from exc
            # Auto-selected the GPU and it turned out to be unusable: redo on CPU
            # instead of failing the run.
            if progress_callback is not None:
                progress_callback(f"GPU transcription unavailable ({exc}); retrying on the CPU.")
            self._model = None
            self._resolved_device = "cpu"
            return self._transcribe_once(
                audio_path, language=language, progress_callback=progress_callback
            )

    def _transcribe_once(
        self,
        audio_path: Path,
        *,
        language: str | None,
        progress_callback: ProgressCallback | None,
    ) -> TranscriptionResult:
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
