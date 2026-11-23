"""Pure managed-region engine: (current content, desired regions) -> new content.

Formats: markdown (<!-- maggy:begin id --> blocks), text (# maggy:begin id
blocks), json and toml (managed keys at dotted paths). Region text is the
block body for text formats and canonical JSON of the value for json/toml;
it is what harness.lock hashes.
"""

from __future__ import annotations

import json
from functools import partial
from typing import Any

from maggy.harness.region_errors import RegionError
from maggy.harness.region_keys import REMOVE, canonical
from maggy.harness.regions_json import extract_json, render_json
from maggy.harness.regions_text import extract_text, render_text
from maggy.harness.regions_toml import extract_toml, render_toml

__all__ = ["REMOVE", "RegionError", "extract", "parse_region", "region_text", "render"]

_ENGINES = {
    "markdown": (partial(render_text, "markdown"), partial(extract_text, "markdown")),
    "text": (partial(render_text, "text"), partial(extract_text, "text")),
    "json": (render_json, extract_json),
    "toml": (render_toml, extract_toml),
}
_TEXTUAL = ("markdown", "text")


def render(fmt: str, content: str | None, regions: dict[str, Any]) -> str:
    """New file content with every region set; raises RegionError if unsafe."""
    return _ENGINES[fmt][0](content, regions)


def extract(fmt: str, content: str | None, ids: list[str]) -> dict[str, str | None]:
    """Region text currently on disk for each id (None when absent)."""
    return _ENGINES[fmt][1](content, ids)


def region_text(fmt: str, value: Any) -> str:
    """Region text of a desired value."""
    return str(value) if fmt in _TEXTUAL else canonical(value)


def parse_region(fmt: str, text: str) -> Any:
    """Inverse of region_text: the value to render back."""
    return text if fmt in _TEXTUAL else json.loads(text)
