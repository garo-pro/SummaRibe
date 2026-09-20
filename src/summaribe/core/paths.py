"""Filesystem locations: packaged defaults, user config dir, cache/work dirs."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import platformdirs

APP_NAME = "SummaRibe"
APP_AUTHOR = "SummaRibe"


def packaged_data_dir() -> Path:
    """Root of the read-only data shipped inside the installed package."""
    return Path(str(resources.files("summaribe") / "data"))


def packaged_providers_dir() -> Path:
    return packaged_data_dir() / "providers"


def packaged_prompts_dir() -> Path:
    return packaged_data_dir() / "prompts"


def user_config_dir() -> Path:
    path = Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_providers_dir() -> Path:
    path = user_config_dir() / "providers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_prompts_dir() -> Path:
    path = user_config_dir() / "prompts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_dictionaries_dir() -> Path:
    path = user_config_dir() / "dictionaries"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return user_config_dir() / "settings.json"


def default_work_dir() -> Path:
    path = Path(platformdirs.user_documents_dir()) / "SummaRibe"
    return path


def user_cache_dir() -> Path:
    path = Path(platformdirs.user_cache_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path
