"""Shared test fixtures. Redirects user config dirs into a per-test tmp_path so
tests never read or write the real SummaRibe config on the machine running them.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from summaribe.core import paths

    config_dir = tmp_path / "config"
    monkeypatch.setattr(paths, "user_config_dir", lambda: config_dir)
    return config_dir
