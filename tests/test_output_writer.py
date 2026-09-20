from pathlib import Path

from summaribe.core.config import AppSettings
from summaribe.core.output_writer import write_outputs
from summaribe.core.pipeline import PipelineContext


def _context(tmp_path: Path, **overrides) -> PipelineContext:
    context = PipelineContext(work_dir=tmp_path, settings=AppSettings())
    for key, value in overrides.items():
        setattr(context, key, value)
    return context


def test_writes_txt_files_for_available_fields(tmp_path: Path):
    context = _context(
        tmp_path,
        transcript_raw="raw",
        transcript_improved="improved",
        summary="summary",
    )
    written = write_outputs(tmp_path, context, ["txt"])
    names = {p.name for p in written}
    assert names == {"transcript.raw.txt", "transcript.improved.txt", "summary.md"}
    assert (tmp_path / "transcript.improved.txt").read_text(encoding="utf-8") == "improved"


def test_json_output_includes_segments(tmp_path: Path):
    context = _context(tmp_path, transcript_raw="raw")
    context.metadata["transcript_segments"] = [{"start": 0.0, "end": 1.0, "text": "hi"}]
    written = write_outputs(tmp_path, context, ["json"])
    assert len(written) == 1
    content = written[0].read_text(encoding="utf-8")
    assert '"transcript_raw": "raw"' in content
    assert '"text": "hi"' in content


def test_srt_and_vtt_skipped_without_segments(tmp_path: Path):
    context = _context(tmp_path, transcript_raw="raw")
    written = write_outputs(tmp_path, context, ["srt", "vtt"])
    assert written == []


def test_srt_renders_expected_timestamp_format(tmp_path: Path):
    context = _context(tmp_path, transcript_raw="raw")
    context.metadata["transcript_segments"] = [{"start": 1.5, "end": 3.25, "text": "hello"}]
    written = write_outputs(tmp_path, context, ["srt"])
    content = written[0].read_text(encoding="utf-8")
    assert "00:00:01,500 --> 00:00:03,250" in content
    assert "hello" in content


def test_no_files_written_when_context_empty(tmp_path: Path):
    context = _context(tmp_path)
    written = write_outputs(tmp_path, context, ["txt", "srt", "vtt"])
    assert written == []
