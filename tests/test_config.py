from pathlib import Path

from summaribe.core.config import AppSettings, SettingsManager


def test_settings_manager_creates_defaults_when_no_file(tmp_path: Path):
    manager = SettingsManager(path=tmp_path / "settings.json")
    assert isinstance(manager.settings, AppSettings)
    assert manager.settings.audio_format == "mp3"


def test_settings_manager_save_and_reload_round_trips(tmp_path: Path):
    path = tmp_path / "settings.json"
    manager = SettingsManager(path=path)
    manager.settings.audio_format = "wav"
    manager.settings.ai.temperature = 0.9
    manager.save()

    reloaded = SettingsManager(path=path)
    assert reloaded.settings.audio_format == "wav"
    assert reloaded.settings.ai.temperature == 0.9
