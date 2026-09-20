"""System prompts used for transcript improvement and summarization.

Stored the same way as provider configs: JSON files, packaged defaults layered
under user overrides/additions, editable from the GUI.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from summaribe.core.layered_store import IdentifiedModel, LayeredJSONStore
from summaribe.core.paths import packaged_prompts_dir, user_prompts_dir

PromptCategory = Literal["improve", "summarize"]


class SystemPrompt(IdentifiedModel):
    category: PromptCategory
    description: str = ""
    content: str = Field(..., description="The system prompt text sent to the AI provider.")


class PromptStore(LayeredJSONStore[SystemPrompt]):
    def __init__(self) -> None:
        super().__init__(SystemPrompt, packaged_prompts_dir(), user_prompts_dir())

    def list_by_category(self, category: PromptCategory) -> list[SystemPrompt]:
        return [p for p in self.list() if p.category == category]
