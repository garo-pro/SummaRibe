"""Command-line interface. Every pipeline step is its own subcommand, and
`run` chains them together, mirroring how the GUI and `Pipeline` class work.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from summaribe.ai.prompts import PromptStore
from summaribe.ai.registry import ProviderStore
from summaribe.core.config import SettingsManager
from summaribe.core.pipeline import Pipeline, PipelineContext, PipelineStep
from summaribe.dictionary.filter import Dictionary, DictionaryStore
from summaribe.steps import DownloadStep, ImproveStep, SummarizeStep, TranscribeStep

app = typer.Typer(
    no_args_is_help=True, help="SummaRibe: download, transcribe, improve, and summarize audio."
)
providers_app = typer.Typer(no_args_is_help=True, help="Manage AI provider configs.")
prompts_app = typer.Typer(no_args_is_help=True, help="Manage system prompts.")
dictionary_app = typer.Typer(no_args_is_help=True, help="Manage word-replacement dictionaries.")
settings_app = typer.Typer(no_args_is_help=True, help="View and edit application settings.")
app.add_typer(providers_app, name="providers")
app.add_typer(prompts_app, name="prompts")
app.add_typer(dictionary_app, name="dictionary")
app.add_typer(settings_app, name="settings")

console = Console()

STEP_BY_NAME: dict[str, Callable[[], PipelineStep]] = {
    "download": DownloadStep,
    "transcribe": TranscribeStep,
    "improve": ImproveStep,
    "summarize": SummarizeStep,
}


def _progress_printer(step_name: str, message: str) -> None:
    console.print(f"[bold cyan]{step_name}[/bold cyan] {message}")


def _load_context(work_dir: Path) -> PipelineContext:
    manager = SettingsManager()
    return PipelineContext(work_dir=work_dir, settings=manager.settings)


def _write_text(path: Path | None, text: str) -> None:
    if path is None:
        console.print(text)
        return
    path.write_text(text, encoding="utf-8")
    console.print(f"[green]Wrote {path}[/green]")


@app.command()
def download(
    url: str,
    work_dir: Annotated[Path, typer.Option(help="Directory audio is downloaded into.")] = Path(),
) -> None:
    """Download a URL's audio track with yt-dlp."""
    context = _load_context(work_dir)
    context.source_url = url
    context = DownloadStep()(context, on_progress=_progress_printer)
    console.print(f"[green]Audio saved to {context.audio_path}[/green]")


@app.command()
def transcribe(
    audio_path: Path,
    out: Annotated[
        Path | None, typer.Option(help="Write transcript text here instead of stdout.")
    ] = None,
    provider: Annotated[
        str | None, typer.Option(help="Override the default transcription provider.")
    ] = None,
) -> None:
    """Transcribe an audio file."""
    context = _load_context(audio_path.parent)
    context.audio_path = audio_path
    if provider:
        context.settings.transcription.default_provider = provider
    context = TranscribeStep()(context, on_progress=_progress_printer)
    _write_text(out, context.transcript_raw or "")


@app.command()
def improve(
    transcript_path: Path,
    out: Annotated[Path | None, typer.Option()] = None,
    provider: Annotated[str | None, typer.Option(help="AI provider id.")] = None,
    prompt: Annotated[str | None, typer.Option(help="System prompt id.")] = None,
) -> None:
    """Run the AI transcript-cleanup pass on an existing transcript file."""
    context = _load_context(transcript_path.parent)
    context.transcript_raw = transcript_path.read_text(encoding="utf-8")
    if provider:
        context.settings.ai.improve_provider_id = provider
    if prompt:
        context.settings.ai.improve_prompt_id = prompt
    context = ImproveStep()(context, on_progress=_progress_printer)
    _write_text(out, context.transcript_improved or "")


@app.command()
def summarize(
    transcript_path: Path,
    out: Annotated[Path | None, typer.Option()] = None,
    provider: Annotated[str | None, typer.Option(help="AI provider id.")] = None,
    prompt: Annotated[str | None, typer.Option(help="System prompt id.")] = None,
) -> None:
    """Summarize an existing (ideally already-improved) transcript file."""
    context = _load_context(transcript_path.parent)
    context.transcript_raw = transcript_path.read_text(encoding="utf-8")
    if provider:
        context.settings.ai.summarize_provider_id = provider
    if prompt:
        context.settings.ai.summarize_prompt_id = prompt
    context = SummarizeStep()(context, on_progress=_progress_printer)
    _write_text(out, context.summary or "")


@app.command()
def run(
    url: str,
    work_dir: Annotated[
        Path, typer.Option(help="Directory intermediate and output files go into.")
    ] = Path(),
    steps: Annotated[
        str,
        typer.Option(
            help="Comma-separated subset/order of: download,transcribe,improve,summarize."
        ),
    ] = "download,transcribe,improve,summarize",
    out_dir: Annotated[
        Path | None, typer.Option(help="Write transcript/summary text files here.")
    ] = None,
) -> None:
    """Chain multiple steps together starting from a URL."""
    step_names = [s.strip() for s in steps.split(",") if s.strip()]
    unknown = [s for s in step_names if s not in STEP_BY_NAME]
    if unknown:
        raise typer.BadParameter(f"Unknown step(s): {unknown}. Choose from {list(STEP_BY_NAME)}.")

    context = _load_context(work_dir)
    context.source_url = url
    pipeline = Pipeline([STEP_BY_NAME[name]() for name in step_names])
    context = pipeline.run(context, on_progress=_progress_printer)

    destination = out_dir or work_dir
    destination.mkdir(parents=True, exist_ok=True)
    if context.transcript_raw:
        (destination / "transcript.raw.txt").write_text(context.transcript_raw, encoding="utf-8")
    if context.transcript_improved:
        (destination / "transcript.improved.txt").write_text(
            context.transcript_improved, encoding="utf-8"
        )
    if context.summary:
        (destination / "summary.md").write_text(context.summary, encoding="utf-8")
    console.print(f"[green]Done. Output written under {destination}[/green]")


@app.command()
def gui() -> None:
    """Launch the wxPython GUI."""
    try:
        from summaribe.gui.app import main as gui_main
    except ImportError as exc:
        console.print(
            "[red]wxPython is not installed. Install the 'gui' extra: uv sync --extra gui[/red]"
        )
        raise typer.Exit(code=1) from exc

    gui_main()


# --- providers ---------------------------------------------------------


@providers_app.command("list")
def providers_list() -> None:
    store = ProviderStore()
    for provider in store.list():
        marker = "(default)" if store.is_default(provider.id) else "(custom)"
        url = f"{provider.base_url}{provider.endpoint}"
        console.print(f"[bold]{provider.id}[/bold] {marker} - {provider.name}: {url}")


@providers_app.command("show")
def providers_show(provider_id: str) -> None:
    provider = ProviderStore().get(provider_id)
    console.print_json(provider.model_dump_json())


@providers_app.command("import")
def providers_import(path: Path) -> None:
    """Create or overwrite a provider from a JSON file matching the provider schema."""
    from summaribe.ai.schema import ProviderConfig

    config = ProviderConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))
    ProviderStore().save(config)
    console.print(f"[green]Saved provider {config.id!r}.[/green]")


@providers_app.command("delete")
def providers_delete(provider_id: str) -> None:
    ProviderStore().delete(provider_id)
    console.print(f"[green]Deleted user override for {provider_id!r}.[/green]")


# --- prompts -------------------------------------------------------------


@prompts_app.command("list")
def prompts_list(category: Annotated[str | None, typer.Option()] = None) -> None:
    store = PromptStore()
    items = store.list_by_category(category) if category else store.list()  # type: ignore[arg-type]
    for prompt in items:
        console.print(f"[bold]{prompt.id}[/bold] ({prompt.category}) - {prompt.name}")


@prompts_app.command("show")
def prompts_show(prompt_id: str) -> None:
    prompt = PromptStore().get(prompt_id)
    console.print_json(prompt.model_dump_json())


@prompts_app.command("import")
def prompts_import(path: Path) -> None:
    from summaribe.ai.prompts import SystemPrompt

    prompt = SystemPrompt.model_validate(json.loads(path.read_text(encoding="utf-8")))
    PromptStore().save(prompt)
    console.print(f"[green]Saved prompt {prompt.id!r}.[/green]")


@prompts_app.command("delete")
def prompts_delete(prompt_id: str) -> None:
    PromptStore().delete(prompt_id)
    console.print(f"[green]Deleted user override for {prompt_id!r}.[/green]")


# --- dictionary ------------------------------------------------------------


@dictionary_app.command("list")
def dictionary_list() -> None:
    for dictionary in DictionaryStore().list():
        console.print(
            f"[bold]{dictionary.id}[/bold] - {dictionary.name} ({len(dictionary.entries)} entries)"
        )


@dictionary_app.command("import")
def dictionary_import(path: Path) -> None:
    dictionary = Dictionary.model_validate(json.loads(path.read_text(encoding="utf-8")))
    DictionaryStore().save(dictionary)
    console.print(f"[green]Saved dictionary {dictionary.id!r}.[/green]")


@dictionary_app.command("delete")
def dictionary_delete(dictionary_id: str) -> None:
    DictionaryStore().delete(dictionary_id)
    console.print(f"[green]Deleted dictionary {dictionary_id!r}.[/green]")


# --- settings ----------------------------------------------------------


@settings_app.command("show")
def settings_show() -> None:
    console.print_json(SettingsManager().settings.model_dump_json())


@settings_app.command("path")
def settings_path() -> None:
    console.print(str(SettingsManager().path))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
