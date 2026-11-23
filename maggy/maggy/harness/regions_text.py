"""Managed blocks in Markdown / plain text, delimited by comment markers.

Everything outside a block is preserved byte for byte; a missing block is
appended at the end of the file.
"""

from __future__ import annotations

import re

from maggy.harness.region_errors import RegionError

MARKERS = {
    "markdown": ("<!-- maggy:begin {} -->", "<!-- maggy:end {} -->"),
    "text": ("# maggy:begin {}", "# maggy:end {}"),
}


def _markers(fmt: str, rid: str) -> tuple[str, str]:
    begin, end = MARKERS[fmt]
    return begin.format(rid), end.format(rid)


def _find(fmt: str, content: str, rid: str) -> re.Match | None:
    begin, end = (re.escape(m) for m in _markers(fmt, rid))
    found = re.search(rf"(?ms)^{begin}\r?\n(.*?)^{end}(?=\r?$)", content)
    if found is None and re.search(rf"(?m)^{begin}\r?$", content):
        raise RegionError(f"managed block '{rid}' has a begin marker but no end marker")
    return found


def extract_text(fmt: str, content: str | None, ids: list[str]) -> dict[str, str | None]:
    """Body of each managed block (None when the block is absent)."""
    out: dict[str, str | None] = {}
    for rid in ids:
        found = _find(fmt, content, rid) if content else None
        body = found.group(1) if found else None
        out[rid] = body.removesuffix("\n").removesuffix("\r") if found else None
    return out


def render_text(fmt: str, content: str | None, regions: dict[str, str]) -> str:
    """Replace (or append) each managed block; never touch other bytes."""
    text = content or ""
    for rid, body in regions.items():
        text = _upsert(fmt, text, (rid, str(body)))
    return text


def _upsert(fmt: str, text: str, region: tuple[str, str]) -> str:
    rid, body = region
    begin, end = _markers(fmt, rid)
    block = f"{begin}\n{body}\n{end}"
    found = _find(fmt, text, rid)
    if found:
        return text[: found.start()] + block + text[found.end():]
    if not text:
        return block + "\n"
    sep = "" if text.endswith("\n") else "\n"
    return f"{text}{sep}\n{block}\n"
