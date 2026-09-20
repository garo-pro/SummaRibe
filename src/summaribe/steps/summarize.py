"""Step 4: summarize the transcript using an AI provider and system prompt.

Uses the improved transcript when available, falling back to the raw one so
this step can run standalone right after transcription.
"""

from __future__ import annotations

from summaribe.ai.prompts import PromptStore
from summaribe.ai.registry import ProviderStore
from summaribe.core.exceptions import StepInputError
from summaribe.core.pipeline import PipelineContext, PipelineStep, ProgressCallback


class SummarizeStep(PipelineStep):
    name = "summarize"
    requires = ()
    produces = ("summary",)

    def validate(self, context: PipelineContext) -> None:
        if context.transcript_improved is None and context.transcript_raw is None:
            raise StepInputError(
                "Step 'summarize' requires transcript_improved or transcript_raw to be set."
            )

    def run(
        self, context: PipelineContext, on_progress: ProgressCallback | None = None
    ) -> PipelineContext:
        source_text = context.transcript_improved or context.transcript_raw
        assert source_text is not None  # guaranteed by `validate`
        ai_settings = context.settings.ai
        client = ProviderStore().client_for(
            ai_settings.summarize_provider_id,
            stream=ai_settings.streaming,
            timeout_seconds=ai_settings.timeout_seconds,
        )
        prompt = PromptStore().get(ai_settings.summarize_prompt_id)

        def _on_token(token: str) -> None:
            if on_progress is not None:
                on_progress(self.name, token)

        extra_variables: dict[str, object] = {
            "temperature": ai_settings.temperature,
            "max_tokens": ai_settings.max_tokens,
        }
        if ai_settings.summarize_model:
            extra_variables["model"] = ai_settings.summarize_model
        result = client.complete(
            system_prompt=prompt.content,
            user_prompt=source_text,
            extra_variables=extra_variables,
            on_token=_on_token,
        )
        context.summary = result.strip()
        return context
