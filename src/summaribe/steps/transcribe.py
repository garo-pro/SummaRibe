"""Step 2: run a transcription provider over the downloaded audio.

If dictionary filtering is enabled in settings, the configured dictionaries
are applied to the raw transcript before it is stored on the context.
"""

from __future__ import annotations

from summaribe.core.pipeline import PipelineContext, PipelineStep, ProgressCallback
from summaribe.dictionary.filter import DictionaryStore, apply_dictionaries
from summaribe.transcription.registry import create_provider


class TranscribeStep(PipelineStep):
    name = "transcribe"
    requires = ("audio_path",)
    produces = ("transcript_raw",)

    def run(
        self, context: PipelineContext, on_progress: ProgressCallback | None = None
    ) -> PipelineContext:
        settings = context.settings.transcription
        provider = create_provider(
            settings.default_provider,
            model=settings.model,
            model_path=settings.model_path,
            device=settings.device,
            compute_type=settings.compute_type,
        )

        def _progress(message: str) -> None:
            if on_progress is not None:
                on_progress(self.name, message)

        assert context.audio_path is not None  # guaranteed by `requires`
        result = provider.transcribe(
            context.audio_path, language=settings.language, progress_callback=_progress
        )
        text = result.text

        dict_settings = context.settings.dictionary
        if dict_settings.enabled and dict_settings.active_dictionary_ids:
            store = DictionaryStore()
            dictionaries = [store.get(did) for did in dict_settings.active_dictionary_ids]
            text = apply_dictionaries(text, dictionaries)

        context.transcript_raw = text
        context.metadata["transcript_language"] = result.language
        context.metadata["transcript_segments"] = [
            segment.model_dump() for segment in result.segments
        ]
        return context
