"""Writes a completed pipeline run's results out in the formats requested by
`AppSettings.output_formats` (txt/srt/vtt/json). This is what makes that
setting do something rather than just being recorded and ignored.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from summaribe.core.config import OutputFormat
from summaribe.core.pipeline import PipelineContext


def _srt_timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _vtt_timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _segments(context: PipelineContext) -> list[dict[str, Any]]:
    segments = context.metadata.get("transcript_segments") or []
    return list(segments)


def render_srt(context: PipelineContext) -> str | None:
    segments = _segments(context)
    if not segments:
        return None
    lines = []
    for index, segment in enumerate(segments, start=1):
        lines.append(str(index))
        lines.append(f"{_srt_timestamp(segment['start'])} --> {_srt_timestamp(segment['end'])}")
        lines.append(segment["text"].strip())
        lines.append("")
    return "\n".join(lines)


def render_vtt(context: PipelineContext) -> str | None:
    segments = _segments(context)
    if not segments:
        return None
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.append(f"{_vtt_timestamp(segment['start'])} --> {_vtt_timestamp(segment['end'])}")
        lines.append(segment["text"].strip())
        lines.append("")
    return "\n".join(lines)


def render_json(context: PipelineContext) -> str:
    return json.dumps(
        {
            "source_url": context.source_url,
            "audio_path": str(context.audio_path) if context.audio_path else None,
            "transcript_raw": context.transcript_raw,
            "transcript_improved": context.transcript_improved,
            "summary": context.summary,
            "segments": _segments(context),
            "metadata": {k: v for k, v in context.metadata.items() if k != "transcript_segments"},
        },
        indent=2,
    )


def write_outputs(
    destination: Path, context: PipelineContext, formats: list[OutputFormat]
) -> list[Path]:
    """Write every requested format that the context has data for. Returns the
    paths actually written (a format with no underlying data, e.g. srt/vtt
    without segment timings, is silently skipped)."""
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if "txt" in formats:
        if context.transcript_raw:
            path = destination / "transcript.raw.txt"
            path.write_text(context.transcript_raw, encoding="utf-8")
            written.append(path)
        if context.transcript_improved:
            path = destination / "transcript.improved.txt"
            path.write_text(context.transcript_improved, encoding="utf-8")
            written.append(path)
        if context.summary:
            path = destination / "summary.md"
            path.write_text(context.summary, encoding="utf-8")
            written.append(path)

    if "srt" in formats:
        content = render_srt(context)
        if content is not None:
            path = destination / "transcript.srt"
            path.write_text(content, encoding="utf-8")
            written.append(path)

    if "vtt" in formats:
        content = render_vtt(context)
        if content is not None:
            path = destination / "transcript.vtt"
            path.write_text(content, encoding="utf-8")
            written.append(path)

    if "json" in formats:
        path = destination / "result.json"
        path.write_text(render_json(context), encoding="utf-8")
        written.append(path)

    return written
