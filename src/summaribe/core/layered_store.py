"""Generic packaged-defaults + user-overrides JSON store.

Both AI provider configs and system prompts follow the same pattern: a
read-only set of defaults ships inside the package's ``data/`` folder, and the
user can add or override entries from the GUI or by hand-editing JSON in their
config directory. This class implements that layering once so both stores stay
tiny and consistent.

Resolution order: user directory entries take precedence over packaged
defaults with the same id. Deleting a user override that shadows a packaged
default reverts to the default; deleting a user-only entry removes it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

from summaribe.core.exceptions import ConfigError, RegistryError


class IdentifiedModel(BaseModel):
    """Base for anything stored by id in a `LayeredJSONStore` (providers, prompts)."""

    id: str
    name: str


ModelT = TypeVar("ModelT", bound=IdentifiedModel)


class LayeredJSONStore(Generic[ModelT]):
    def __init__(self, model_cls: type[ModelT], packaged_dir: Path, user_dir: Path) -> None:
        self._model_cls = model_cls
        self._packaged_dir = packaged_dir
        self._user_dir = user_dir

    def _load_dir(self, directory: Path) -> dict[str, ModelT]:
        items: dict[str, ModelT] = {}
        if not directory.is_dir():
            return items
        for path in sorted(directory.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                item = self._model_cls.model_validate(raw)
            except Exception as exc:
                raise ConfigError(f"Invalid config file {path}: {exc}") from exc
            items[item.id] = item
        return items

    def list(self) -> list[ModelT]:
        merged = self._load_dir(self._packaged_dir)
        merged.update(self._load_dir(self._user_dir))
        return sorted(merged.values(), key=lambda item: item.name)

    def get(self, item_id: str) -> ModelT:
        for item in self.list():
            if item.id == item_id:
                return item
        raise RegistryError(f"No entry with id {item_id!r}")

    def is_default(self, item_id: str) -> bool:
        return item_id in self._load_dir(self._packaged_dir)

    def save(self, item: ModelT) -> Path:
        """Write ``item`` into the user directory (creating or overriding it)."""
        self._user_dir.mkdir(parents=True, exist_ok=True)
        path = self._user_dir / f"{item.id}.json"
        path.write_text(item.model_dump_json(indent=2), encoding="utf-8")
        return path

    def delete(self, item_id: str) -> None:
        user_path = self._user_dir / f"{item_id}.json"
        if user_path.exists():
            user_path.unlink()
            return
        if self.is_default(item_id):
            raise ConfigError(f"{item_id!r} is a packaged default with no user override to remove.")
        raise RegistryError(f"No entry with id {item_id!r}")
