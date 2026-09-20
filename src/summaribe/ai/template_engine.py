"""Tiny nested-template engine used to render AI provider request payloads.

A template is an arbitrary JSON-like structure (dict / list / str / number / bool /
None) where string values may contain ``{{dotted.key}}`` placeholders.

Two substitution modes are supported:

* **Full-token**: a string that is *exactly* ``{{key}}`` is replaced by the raw
  Python value bound to ``key`` (which may itself be a dict, list, bool, number,
  or None). This is what lets ``"messages": "{{messages}}"`` splice a whole list
  of message dicts into the payload.
* **Inline**: a string containing a placeholder alongside other text (or several
  placeholders) has each occurrence replaced by ``str(value)``.

Lookups use dotted paths (``a.b.c``) to reach nested variables.
"""

from __future__ import annotations

import re
from typing import Any

from summaribe.core.exceptions import MissingTemplateVariableError, ResponseExtractionError

_FULL_TOKEN_RE = re.compile(r"^\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}$")
_INLINE_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")

_MISSING = object()


def _lookup(variables: dict[str, Any], dotted_key: str) -> Any:
    current: Any = variables
    for part in dotted_key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return _MISSING
    return current


def render(node: Any, variables: dict[str, Any]) -> Any:
    """Recursively render a template ``node`` against ``variables``.

    Raises ``MissingTemplateVariableError`` if a placeholder has no matching
    variable. Non-string leaves (numbers, bools, None) pass through unchanged.
    """
    if isinstance(node, str):
        full_match = _FULL_TOKEN_RE.match(node)
        if full_match:
            key = full_match.group(1)
            value = _lookup(variables, key)
            if value is _MISSING:
                raise MissingTemplateVariableError(f"Missing template variable: {key!r}")
            return value

        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            value = _lookup(variables, key)
            if value is _MISSING:
                raise MissingTemplateVariableError(f"Missing template variable: {key!r}")
            return "" if value is None else str(value)

        return _INLINE_TOKEN_RE.sub(_replace, node)
    if isinstance(node, dict):
        return {key: render(value, variables) for key, value in node.items()}
    if isinstance(node, list):
        return [render(item, variables) for item in node]
    return node


def extract(data: Any, path: str) -> Any:
    """Resolve a dotted ``path`` (numeric segments index into lists) within ``data``."""
    current = data
    for part in path.split("."):
        try:
            if isinstance(current, list):
                current = current[int(part)]
            elif isinstance(current, dict):
                current = current[part]
            else:
                raise ResponseExtractionError(
                    f"Cannot resolve {path!r}: reached non-container value at {part!r}"
                )
        except (KeyError, IndexError, ValueError) as exc:
            raise ResponseExtractionError(
                f"Cannot resolve {path!r}: no {part!r} in response"
            ) from exc
    return current


def try_extract(data: Any, path: str | None) -> Any | None:
    """Like ``extract`` but returns ``None`` instead of raising (for optional paths)."""
    if not path:
        return None
    try:
        return extract(data, path)
    except ResponseExtractionError:
        return None
