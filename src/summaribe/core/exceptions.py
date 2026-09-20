"""Exception hierarchy for SummaRibe."""

from __future__ import annotations


class SummaRibeError(Exception):
    """Base class for all SummaRibe errors."""


class StepInputError(SummaRibeError):
    """Raised when a pipeline step is run without its required inputs."""


class DownloadError(SummaRibeError):
    """Raised when audio download via yt-dlp fails."""


class TranscriptionError(SummaRibeError):
    """Raised when a transcription provider fails to produce a result."""


class ProviderUnavailableError(TranscriptionError):
    """Raised when a transcription provider's dependencies are not installed."""


class ModelLoadError(TranscriptionError):
    """Raised when a transcription model fails to load from disk or hub."""


class AIProviderError(SummaRibeError):
    """Raised when an AI provider HTTP request fails or returns malformed data."""


class TemplateError(SummaRibeError):
    """Base class for template-rendering errors."""


class MissingTemplateVariableError(TemplateError):
    """Raised when a template references a variable that was not supplied."""


class ResponseExtractionError(TemplateError):
    """Raised when a configured response path cannot be resolved in a response."""


class ConfigError(SummaRibeError):
    """Raised for invalid or missing configuration (providers, prompts, settings)."""


class RegistryError(SummaRibeError):
    """Raised for lookups against unknown registry keys."""
