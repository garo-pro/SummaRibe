"""Chainable pipeline: each step can run standalone or as part of a sequence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from summaribe.core.config import AppSettings
from summaribe.core.exceptions import StepInputError

ProgressCallback = Callable[[str, str], None]  # (step_name, message)


class PipelineContext(BaseModel):
    """The data that flows between steps. Fields start as ``None`` and are
    filled in as steps run; a step declares which fields it needs and which
    it produces so it can be validated and run independently."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    work_dir: Path
    settings: AppSettings = Field(default_factory=AppSettings)

    source_url: str | None = None
    audio_path: Path | None = None
    transcript_raw: str | None = None
    transcript_improved: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def emit(self, step_name: str, message: str, on_progress: ProgressCallback | None) -> None:
        if on_progress is not None:
            on_progress(step_name, message)


class PipelineStep(ABC):
    """Base class for one pipeline stage.

    ``requires``/``produces`` name attributes on ``PipelineContext``; calling a
    step directly (``step(context)``) validates that required inputs are
    present, which is what lets each step run standalone in the CLI as well as
    chained inside a ``Pipeline``.
    """

    name: ClassVar[str]
    requires: ClassVar[tuple[str, ...]] = ()
    produces: ClassVar[tuple[str, ...]] = ()

    def validate(self, context: PipelineContext) -> None:
        missing = [field for field in self.requires if getattr(context, field) is None]
        if missing:
            raise StepInputError(
                f"Step {self.name!r} requires {missing}, but they are not set on the context. "
                f"Run an earlier step first or provide them explicitly."
            )

    @abstractmethod
    def run(
        self, context: PipelineContext, on_progress: ProgressCallback | None = None
    ) -> PipelineContext: ...

    def __call__(
        self, context: PipelineContext, on_progress: ProgressCallback | None = None
    ) -> PipelineContext:
        self.validate(context)
        context.emit(self.name, "started", on_progress)
        result = self.run(context, on_progress=on_progress)
        result.emit(self.name, "finished", on_progress)
        return result


class Pipeline:
    """Runs an ordered sequence of steps against one shared context."""

    def __init__(self, steps: Sequence[PipelineStep]) -> None:
        self.steps = list(steps)

    def run(
        self, context: PipelineContext, on_progress: ProgressCallback | None = None
    ) -> PipelineContext:
        for step in self.steps:
            context = step(context, on_progress=on_progress)
        return context
