from pathlib import Path

from typer.testing import CliRunner

from summaribe.cli import app

runner = CliRunner()


def test_providers_list_shows_defaults():
    result = runner.invoke(app, ["providers", "list"])
    assert result.exit_code == 0
    assert "ollama" in result.stdout
    assert "anthropic" in result.stdout


def test_prompts_list_filters_by_category():
    result = runner.invoke(app, ["prompts", "list", "--category", "improve"])
    assert result.exit_code == 0
    assert "improve_default" in result.stdout
    assert "summarize_default" not in result.stdout


def test_dictionary_list_empty_by_default():
    result = runner.invoke(app, ["dictionary", "list"])
    assert result.exit_code == 0
    assert result.stdout.strip() == ""


def test_settings_show_prints_json():
    result = runner.invoke(app, ["settings", "show"])
    assert result.exit_code == 0
    assert "audio_format" in result.stdout


def test_prompts_list_rejects_unknown_category():
    result = runner.invoke(app, ["prompts", "list", "--category", "not-a-category"])
    assert result.exit_code != 0


def test_run_requires_url_when_download_step_included(tmp_path: Path):
    result = runner.invoke(app, ["run", "--work-dir", str(tmp_path)])
    assert result.exit_code != 0


def test_run_requires_file_when_download_step_excluded(tmp_path: Path):
    result = runner.invoke(app, ["run", "--work-dir", str(tmp_path), "--steps", "transcribe"])
    assert result.exit_code != 0


def test_run_chains_from_local_transcript_file(monkeypatch, tmp_path: Path):
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_text("raw text", encoding="utf-8")

    from summaribe.ai.provider import AIClient

    monkeypatch.setattr(AIClient, "complete", lambda self, **kwargs: "cleaned")

    result = runner.invoke(
        app,
        [
            "run",
            "--file",
            str(transcript_path),
            "--work-dir",
            str(tmp_path),
            "--steps",
            "improve,summarize",
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "transcript.improved.txt").read_text(encoding="utf-8") == "cleaned"
    assert (tmp_path / "summary.md").read_text(encoding="utf-8") == "cleaned"


def test_improve_step_uses_ai_provider(monkeypatch, tmp_path: Path):
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_text("raw text", encoding="utf-8")

    def fake_complete(self, *, system_prompt, user_prompt, **kwargs):
        assert user_prompt == "raw text"
        return "cleaned text"

    from summaribe.ai.provider import AIClient

    monkeypatch.setattr(AIClient, "complete", fake_complete)

    result = runner.invoke(app, ["improve", str(transcript_path)])
    assert result.exit_code == 0
    assert "cleaned text" in result.stdout
