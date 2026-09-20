from pathlib import Path

import pytest

from summaribe.core.config import AppSettings
from summaribe.core.exceptions import StepInputError
from summaribe.core.pipeline import Pipeline, PipelineContext, PipelineStep


class _UppercaseStep(PipelineStep):
    name = "uppercase"
    requires = ("transcript_raw",)
    produces = ("transcript_improved",)

    def run(self, context, on_progress=None):
        context.transcript_improved = context.transcript_raw.upper()
        return context


class _CountStep(PipelineStep):
    name = "count"
    requires = ("transcript_improved",)
    produces = ("summary",)

    def run(self, context, on_progress=None):
        context.summary = str(len(context.transcript_improved))
        return context


@pytest.fixture
def context(tmp_path: Path) -> PipelineContext:
    return PipelineContext(work_dir=tmp_path, settings=AppSettings())


def test_step_raises_when_required_input_missing(context):
    with pytest.raises(StepInputError):
        _UppercaseStep()(context)


def test_step_runs_standalone_when_input_present(context):
    context.transcript_raw = "hello"
    result = _UppercaseStep()(context)
    assert result.transcript_improved == "HELLO"


def test_pipeline_chains_steps_in_order(context):
    context.transcript_raw = "hi"
    pipeline = Pipeline([_UppercaseStep(), _CountStep()])
    result = pipeline.run(context)
    assert result.transcript_improved == "HI"
    assert result.summary == "2"


def test_progress_callback_receives_step_events(context):
    context.transcript_raw = "hi"
    events: list[tuple[str, str]] = []
    _UppercaseStep()(context, on_progress=lambda name, msg: events.append((name, msg)))
    assert ("uppercase", "started") in events
    assert ("uppercase", "finished") in events
