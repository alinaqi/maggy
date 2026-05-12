"""Document text extraction for chat file processing."""

from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

_DOC_EXTS = frozenset({
    ".csv", ".json", ".txt", ".md", ".log",
    ".xlsx", ".xls", ".docx", ".pdf",
})
_IMAGE_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
})
_MAX_CHARS = 8000
_DOC_PATH_RE = re.compile(
    r"""((?:/|~/)[\w./\- ]+\.(?:"""
    + "|".join(e.lstrip(".") for e in _DOC_EXTS)
    + r"""))""",
    re.IGNORECASE,
)


def extract_document_path(
    message: str,
) -> tuple[str, str] | None:
    """Detect a document file path in a chat message.

    Returns (resolved_path, remaining_prompt) or None.
    """
    m = _DOC_PATH_RE.search(message)
    if not m:
        return None
    raw = m.group(1).replace("\\ ", " ")
    p = Path(raw).expanduser().resolve()
    if not p.exists():
        return None
    if p.suffix.lower() in _IMAGE_EXTS:
        return None
    if p.suffix.lower() not in _DOC_EXTS:
        return None
    prompt = (message[:m.start()] + message[m.end():]).strip()
    prompt = re.sub(r"\s{2,}", " ", prompt)
    return str(p), prompt or None


def extract_text(path: str) -> str:
    """Extract text content from a document file."""
    p = Path(path)
    ext = p.suffix.lower()
    extractors = {
        ".csv": _extract_csv,
        ".json": _extract_json,
        ".txt": _extract_txt,
        ".md": _extract_txt,
        ".log": _extract_txt,
        ".xlsx": _extract_excel,
        ".xls": _extract_excel,
        ".docx": _extract_docx,
        ".pdf": _extract_pdf,
    }
    fn = extractors.get(ext)
    if not fn:
        return f"Error: .{ext} is not supported."
    try:
        text = fn(p)
    except Exception as e:
        return f"Error extracting {p.name}: {e}"
    return _truncate(text)


def _truncate(text: str) -> str:
    if len(text) <= _MAX_CHARS:
        return text
    return text[:_MAX_CHARS] + "\n\n[truncated]"


def _extract_csv(p: Path) -> str:
    with p.open(newline="") as f:
        reader = csv.reader(f)
        rows = [", ".join(row) for row in reader]
    return "\n".join(rows[:200])


def _extract_json(p: Path) -> str:
    data = json.loads(p.read_text())
    return json.dumps(data, indent=2)


def _extract_txt(p: Path) -> str:
    return p.read_text(errors="replace")


def _extract_excel(p: Path) -> str:
    from maggy.services.auto_deps import ensure_import
    openpyxl = ensure_import("openpyxl")
    wb = openpyxl.load_workbook(p, read_only=True)
    lines = []
    for sheet in wb.sheetnames[:3]:
        ws = wb[sheet]
        lines.append(f"## Sheet: {sheet}")
        for row in ws.iter_rows(max_row=100, values_only=True):
            vals = [str(c) if c is not None else "" for c in row]
            lines.append(", ".join(vals))
    wb.close()
    return "\n".join(lines)


def _extract_docx(p: Path) -> str:
    from maggy.services.auto_deps import ensure_import
    docx = ensure_import("docx", pip_name="python-docx")
    doc = docx.Document(str(p))
    return "\n\n".join(para.text for para in doc.paragraphs)


def _extract_pdf(p: Path) -> str:
    from maggy.services.auto_deps import ensure_import
    pymupdf = ensure_import("pymupdf")
    doc = pymupdf.open(str(p))
    pages = [doc[i].get_text() for i in range(min(len(doc), 20))]
    doc.close()
    return "\n\n".join(pages)


async def process_document(
    path: str,
    prompt: str | None,
    session,
) -> AsyncGenerator[dict, None]:
    """Extract text from document and forward to Claude."""
    from maggy.services.chat_stream import stream_message

    text = extract_text(path)
    if text.startswith("Error:"):
        yield {"type": "error", "content": text}
        return
    name = Path(path).name
    enriched = (
        f"Content of {name}:\n\n{text}\n\n"
        f"{prompt or 'Analyze this document.'}"
    )
    async for chunk in stream_message(session, enriched):
        yield chunk
