"""Step 3: clean up the raw transcript using an AI provider and system prompt."""

from __future__ import annotations

from summaribe.ai.prompts import PromptStore
from summaribe.ai.registry import ProviderStore
from summaribe.core.pipeline import PipelineContext, PipelineStep, ProgressCallback


class ImproveStep(PipelineStep):
    name = "improve"
    requires = ("transcript_raw",)
    produces = ("transcript_improved",)

    def run(
        self, context: PipelineContext, on_progress: ProgressCallback | None = None
    ) -> PipelineContext:
        ai_settings = context.settings.ai
        client = ProviderStore().client_for(
            ai_settings.improve_provider_id,
            stream=ai_settings.streaming,
            timeout_seconds=ai_settings.timeout_seconds,
        )
        prompt = PromptStore().get(ai_settings.improve_prompt_id)

        def _on_token(token: str) -> None:
            if on_progress is not None:
                on_progress(self.name, token)

        assert context.transcript_raw is not None  # guaranteed by `requires`
        extra_variables: dict[str, object] = {
            "temperature": ai_settings.temperature,
            "max_tokens": ai_settings.max_tokens,
        }
        if ai_settings.improve_model:
            extra_variables["model"] = ai_settings.improve_model
        result = client.complete(
            system_prompt=prompt.content,
            user_prompt=context.transcript_raw,
            extra_variables=extra_variables,
            on_token=_on_token,
        )
        context.transcript_improved = result.strip()
        return context
