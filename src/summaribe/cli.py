"""Command-line interface. Every pipeline step is its own subcommand, and
`run` chains them together, mirroring how the GUI and `Pipeline` class work.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, get_args

import typer
from rich.console import Console

from summaribe.ai.prompts import PromptCategory, PromptStore
from summaribe.ai.registry import ProviderStore
from summaribe.core.config import SettingsManager
from summaribe.core.logging_setup import configure_logging
from summaribe.core.output_writer import write_outputs
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


@app.callback()
def _main() -> None:
    configure_logging(SettingsManager().settings.log_level)


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
    model: Annotated[
        str | None, typer.Option(help="Override the provider's default model.")
    ] = None,
) -> None:
    """Run the AI transcript-cleanup pass on an existing transcript file."""
    context = _load_context(transcript_path.parent)
    context.transcript_raw = transcript_path.read_text(encoding="utf-8")
    if provider:
        context.settings.ai.improve_provider_id = provider
    if prompt:
        context.settings.ai.improve_prompt_id = prompt
    if model:
        context.settings.ai.improve_model = model
    context = ImproveStep()(context, on_progress=_progress_printer)
    _write_text(out, context.transcript_improved or "")


@app.command()
def summarize(
    transcript_path: Path,
    out: Annotated[Path | None, typer.Option()] = None,
    provider: Annotated[str | None, typer.Option(help="AI provider id.")] = None,
    prompt: Annotated[str | None, typer.Option(help="System prompt id.")] = None,
    model: Annotated[
        str | None, typer.Option(help="Override the provider's default model.")
    ] = None,
) -> None:
    """Summarize an existing (ideally already-improved) transcript file."""
    context = _load_context(transcript_path.parent)
    context.transcript_raw = transcript_path.read_text(encoding="utf-8")
    if provider:
        context.settings.ai.summarize_provider_id = provider
    if prompt:
        context.settings.ai.summarize_prompt_id = prompt
    if model:
        context.settings.ai.summarize_model = model
    context = SummarizeStep()(context, on_progress=_progress_printer)
    _write_text(out, context.summary or "")


@app.command()
def run(
    url: Annotated[
        str | None, typer.Argument(help="URL to download. Required unless --file is given.")
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option(
            help="Start from a local audio file or transcript text file instead of a URL."
        ),
    ] = None,
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
        Path | None, typer.Option(help="Write result files here (defaults to --work-dir).")
    ] = None,
) -> None:
    """Chain multiple steps together, starting from either a URL or a local file."""
    step_names = [s.strip() for s in steps.split(",") if s.strip()]
    unknown = [s for s in step_names if s not in STEP_BY_NAME]
    if unknown:
        raise typer.BadParameter(f"Unknown step(s): {unknown}. Choose from {list(STEP_BY_NAME)}.")

    context = _load_context(work_dir)
    if "download" in step_names:
        if url is None:
            raise typer.BadParameter("A URL is required when 'download' is one of --steps.")
        context.source_url = url
    else:
        if file is None:
            raise typer.BadParameter("--file is required when 'download' is not one of --steps.")
        if file.suffix.lower() in {".txt", ".md"}:
            context.transcript_raw = file.read_text(encoding="utf-8")
        else:
            context.audio_path = file

    pipeline = Pipeline([STEP_BY_NAME[name]() for name in step_names])
    context = pipeline.run(context, on_progress=_progress_printer)

    destination = out_dir or work_dir
    written = write_outputs(destination, context, context.settings.output_formats)

    if not context.settings.keep_intermediate_files:
        if context.audio_path and context.audio_path.exists() and context.transcript_raw:
            context.audio_path.unlink()
        if context.transcript_improved:
            raw_txt = destination / "transcript.raw.txt"
            if raw_txt in written:
                raw_txt.unlink()
                written.remove(raw_txt)

    console.print(
        f"[green]Done. Wrote: {', '.join(str(p) for p in written) or '(nothing)'}[/green]"
    )

    if context.settings.gui.auto_open_output_folder:
        _open_folder(destination)


def _open_folder(path: Path) -> None:
    import subprocess
    import sys

    if sys.platform == "win32":
        subprocess.run(["explorer", str(path)], check=False)
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


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


@providers_app.command("models")
def providers_models(provider_id: str) -> None:
    """List the models a provider reports as available (requires its `models` config)."""
    store = ProviderStore()
    config = store.get(provider_id)
    if config.models is None:
        console.print(
            f"[yellow]Provider {provider_id!r} has no models listing endpoint configured.[/yellow]"
        )
        raise typer.Exit(code=1)
    for model_id in store.client_for(provider_id).list_models():
        console.print(model_id)


@providers_app.command("import")
def providers_import(path: Path) -> None:
    """Create or overwrite a provider from a JSON file matching the provider schema."""
    from summaribe.ai.schema import ProviderConfig

    config = ProviderConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))
    ProviderStore().save(config)
    console.print(f"[green]Saved provider {config.id!r}.[/green]")


@providers_app.command("delete")
def providers_delete(provider_id: str) -> None:
    store = ProviderStore()
    was_override = store.is_default(provider_id)
    store.delete(provider_id)
    if was_override:
        console.print(
            f"[green]Removed override; {provider_id!r} reverted to its packaged default.[/green]"
        )
    else:
        console.print(f"[green]Deleted provider {provider_id!r}.[/green]")


# --- prompts -------------------------------------------------------------


@prompts_app.command("list")
def prompts_list(category: Annotated[str | None, typer.Option()] = None) -> None:
    if category is not None and category not in get_args(PromptCategory):
        raise typer.BadParameter(f"category must be one of {get_args(PromptCategory)}")
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
    store = PromptStore()
    was_override = store.is_default(prompt_id)
    store.delete(prompt_id)
    if was_override:
        console.print(
            f"[green]Removed override; {prompt_id!r} reverted to its packaged default.[/green]"
        )
    else:
        console.print(f"[green]Deleted prompt {prompt_id!r}.[/green]")


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
