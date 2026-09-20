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
