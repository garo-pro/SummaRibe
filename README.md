# SummaRibe

Turn a URL (or a local file) into a clean transcript and a summary:

**download audio → transcribe → AI-improve the transcript → AI-summarize it**

Every step is its own module, runnable standalone or chained together, from either a wxPython desktop GUI or a CLI. Transcription backends (Whisper, Parakeet-TDT, Qwen3-ASR, or your own model) and AI providers (Ollama, llama.cpp, Anthropic, OpenAI, OpenRouter, or your own HTTP endpoint) are all pluggable through JSON config, no code changes required.

## Features

- **Chainable pipeline** - `download`, `transcribe`, `improve`, `summarize` are independent steps. Run all four in order, or run any one of them by itself against an existing file.
- **Pluggable transcription** - Whisper (via faster-whisper), NVIDIA Parakeet-TDT (via NeMo), and Qwen3-ASR (via Transformers) ship built in. Point any of them at a local checkpoint instead of a named model to use a fine-tuned or custom model that shares the same architecture.
- **Template-driven AI providers** - talking to a chat-completion API (local or cloud) is described entirely in JSON: base URL, endpoint, headers, request body template, and where to find the reply in the response. Ollama, llama.cpp, Anthropic, OpenAI, and OpenRouter ship as defaults; add your own by writing (or editing in the GUI) another JSON file. A provider can also optionally describe a models-listing endpoint, which lights up a "Fetch models" picker in Settings.
- **Editable system prompts** - separate prompt libraries for transcript cleanup and summarization, with sensible defaults included and full GUI/CLI editing.
- **Optional dictionary filter** - user-defined find/replace rules for words your transcription model consistently gets wrong (jargon, names, acronyms). Ships with zero entries; it's purely something you build up yourself.
- **wxPython GUI and a full CLI** - the same core pipeline backs both.

## Install

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # core install: CLI + pipeline, no GUI or ASR backends
uv sync --extra gui           # + the wxPython desktop GUI
uv sync --extra whisper       # + faster-whisper
uv sync --extra parakeet      # + NVIDIA NeMo (Parakeet-TDT)
uv sync --extra qwen          # + Transformers (Qwen3-ASR)
uv sync --extra all           # everything
```

Audio extraction requires `ffmpeg` on your `PATH`.

## Usage

### GUI

```bash
uv run summaribe gui
```

Tabs: **Pipeline** (run steps against a URL or file), **Providers**, **Prompts**, **Dictionary**, and **Settings**.

### CLI

Each step works on its own:

```bash
uv run summaribe download "https://example.com/watch?v=..." --work-dir ./out
uv run summaribe transcribe ./out/abc123.mp3 --out ./out/transcript.txt
uv run summaribe improve ./out/transcript.txt --out ./out/improved.txt
uv run summaribe summarize ./out/improved.txt --out ./out/summary.md
```

...or chained in one command:

```bash
uv run summaribe run "https://example.com/watch?v=..." --out-dir ./out
uv run summaribe run "https://example.com/watch?v=..." --steps download,transcribe

# Or start from a local file instead of a URL (no 'download' step, so no URL needed):
uv run summaribe run --file ./out/abc123.mp3 --steps transcribe,improve,summarize
```

`run` writes whichever of `transcript.raw.txt` / `transcript.improved.txt` / `summary.md` / `transcript.srt` / `transcript.vtt` / `result.json` are relevant, based on `settings.output_formats` (`srt`/`vtt` need segment timings, which not every transcription provider produces).

Manage providers, prompts, dictionaries, and settings:

```bash
uv run summaribe providers list
uv run summaribe providers show ollama
uv run summaribe providers import my-provider.json
uv run summaribe prompts list --category improve
uv run summaribe dictionary import my-terms.json
uv run summaribe settings show
```

## Configuring an AI provider

A provider is one JSON file (see `src/summaribe/data/providers/*.json` for the shipped defaults). The request body is a *template*: `"{{name}}"` is replaced with a variable, and a string that is *only* a placeholder (e.g. `"messages": "{{messages}}"`) is replaced with the raw value (a list, bool, number, ...) rather than stringified, so structured data can be spliced in.

```json
{
  "id": "my-server",
  "name": "My llama.cpp server",
  "base_url": "http://localhost:8080",
  "endpoint": "/v1/chat/completions",
  "method": "POST",
  "headers": { "Content-Type": "application/json" },
  "timeout_seconds": 120,
  "stream": false,
  "stream_format": "sse",
  "request_template": {
    "model": "{{model}}",
    "messages": "{{messages}}",
    "temperature": "{{temperature}}",
    "stream": "{{stream}}"
  },
  "response_path": "choices.0.message.content",
  "stream_delta_path": "choices.0.delta.content",
  "variables": { "model": "local-model", "temperature": 0.3, "max_tokens": 2048 }
}
```

`response_path` / `stream_delta_path` are dotted paths (numeric segments index into lists) used to pull the reply text out of the JSON response. For an API key, set `api_key_env` to the name of an environment variable; its value is exposed to templates as `{{api_key}}` (used inside `headers`, typically).

Providers, prompts, and dictionaries are stored as **packaged defaults + user overrides**: editing a default in the GUI/CLI saves your version into your user config directory without touching the installed package; deleting a user override reverts to the shipped default.

### Listing available models

A provider can optionally describe how to list its available models, via a `"models"` field that's either absent/`null` (no such endpoint - the model picker UI just doesn't appear for that provider) or an object like:

```json
"models": {
  "endpoint": "/v1/models",
  "method": "GET",
  "response_list_path": "data",
  "model_id_path": "id"
}
```

`response_list_path` is a dotted path to the array of model objects in the response; `model_id_path` is a dotted path *within each item* to its id. This is enough to describe every provider shipped by default:

| Provider   | Endpoint     | `response_list_path` | `model_id_path` |
|------------|--------------|-----------------------|------------------|
| Ollama     | `/api/tags`  | `models`              | `model`          |
| llama.cpp  | `/v1/models` | `data`                | `id`             |
| Anthropic  | `/v1/models` | `data`                | `id`             |
| OpenAI     | `/v1/models` | `data`                | `id`             |
| OpenRouter | `/v1/models` | `data`                | `id`             |

```bash
uv run summaribe providers models ollama
```

In the GUI's **Settings** tab, the improve/summarize "Model" fields have a *Fetch models* button next to them that calls this endpoint and lets you pick from what the provider actually has available, instead of typing a model id from memory. Leaving the model field blank falls back to the provider's own `variables.model` default.

## Architecture

```
src/summaribe/
  core/            settings, the PipelineStep/Pipeline base classes, shared paths
  ai/              provider schema, template engine, HTTP client, prompt store
  transcription/   TranscriptionProvider base + Whisper/Parakeet/Qwen3-ASR + registry
  steps/           DownloadStep, TranscribeStep, ImproveStep, SummarizeStep
  dictionary/      find/replace filter applied after transcription
  gui/             wxPython panels, one per concern
  data/            packaged default providers and prompts (JSON)
  cli.py           Typer CLI: one subcommand per step, plus `run` to chain them
```

A `PipelineStep` declares the context fields it `requires` and `produces`. Calling a step directly validates its inputs and runs it standalone; a `Pipeline` just calls a list of steps against one shared context in order. This is what makes every step independently runnable *and* chainable without two separate code paths.

## Development

```bash
uv sync --extra all --group dev
uv run pytest                 # unit tests (no real network/model calls)
uv run ruff check .           # lint
uv run ruff format .          # format
uv run mypy src               # strict type checking
uv run pre-commit install     # run the above automatically on commit
```

## License

MIT - see [LICENSE](LICENSE).
