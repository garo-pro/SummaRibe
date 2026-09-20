"""Find/replace dictionaries applied to transcripts after transcription.

Unlike AI providers and prompts, no dictionaries ship by default: this feature
exists purely so a user can teach SummaRibe about words their transcription
model consistently gets wrong (jargon, names, acronyms). Entries are applied in
order, so more specific fixes can be listed after more general ones.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from summaribe.core.exceptions import ConfigError, RegistryError
from summaribe.core.paths import user_dictionaries_dir


class DictionaryEntry(BaseModel):
    find: str
    replace: str
    case_sensitive: bool = False
    whole_word: bool = True


class Dictionary(BaseModel):
    id: str
    name: str
    description: str = ""
    entries: list[DictionaryEntry] = Field(default_factory=list)

    def apply(self, text: str) -> str:
        for entry in self.entries:
            pattern = re.escape(entry.find)
            if entry.whole_word:
                pattern = rf"\b{pattern}\b"
            flags = 0 if entry.case_sensitive else re.IGNORECASE
            text = re.sub(pattern, entry.replace, text, flags=flags)
        return text


class DictionaryStore:
    """Simple JSON-file store; dictionaries are always user data, no packaged defaults."""

    def __init__(self, directory: Path | None = None) -> None:
        self._dir = directory or user_dictionaries_dir()

    def list(self) -> list[Dictionary]:
        self._dir.mkdir(parents=True, exist_ok=True)
        items = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                items.append(
                    Dictionary.model_validate(json.loads(path.read_text(encoding="utf-8")))
                )
            except Exception as exc:
                raise ConfigError(f"Invalid dictionary file {path}: {exc}") from exc
        return items

    def get(self, dictionary_id: str) -> Dictionary:
        for item in self.list():
            if item.id == dictionary_id:
                return item
        raise RegistryError(f"No dictionary with id {dictionary_id!r}")

    def save(self, dictionary: Dictionary) -> Path:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{dictionary.id}.json"
        path.write_text(dictionary.model_dump_json(indent=2), encoding="utf-8")
        return path

    def delete(self, dictionary_id: str) -> None:
        path = self._dir / f"{dictionary_id}.json"
        if not path.exists():
            raise RegistryError(f"No dictionary with id {dictionary_id!r}")
        path.unlink()


def apply_dictionaries(text: str, dictionaries: list[Dictionary]) -> str:
    for dictionary in dictionaries:
        text = dictionary.apply(text)
    return text
