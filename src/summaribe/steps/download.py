"""Step 1: download a URL's audio track via yt-dlp."""

from __future__ import annotations

from typing import Any

from summaribe.core.exceptions import DownloadError
from summaribe.core.pipeline import PipelineContext, PipelineStep, ProgressCallback


class DownloadStep(PipelineStep):
    name = "download"
    requires = ("source_url",)
    produces = ("audio_path",)

    def run(
        self, context: PipelineContext, on_progress: ProgressCallback | None = None
    ) -> PipelineContext:
        import yt_dlp

        context.work_dir.mkdir(parents=True, exist_ok=True)
        audio_format = context.settings.audio_format
        quality = str(context.settings.audio_quality_kbps)
        output_template = str(context.work_dir / "%(id)s.%(ext)s")

        def _hook(status: dict[str, Any]) -> None:
            if on_progress is None:
                return
            if status.get("status") == "downloading":
                pct = status.get("_percent_str", "").strip()
                on_progress(self.name, f"downloading {pct}")
            elif status.get("status") == "finished":
                on_progress(self.name, "download finished, extracting audio")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                    "preferredquality": quality,
                }
            ],
            "progress_hooks": [_hook],
            "quiet": True,
            "noprogress": True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(context.source_url, download=True)
        except Exception as exc:
            raise DownloadError(f"Failed to download {context.source_url!r}: {exc}") from exc

        video_id = info["id"]
        audio_path = context.work_dir / f"{video_id}.{audio_format}"
        if not audio_path.exists():
            raise DownloadError(f"Expected output audio file not found: {audio_path}")

        context.audio_path = audio_path
        context.metadata["title"] = info.get("title")
        context.metadata["source_url"] = context.source_url
        context.metadata["duration"] = info.get("duration")
        return context
