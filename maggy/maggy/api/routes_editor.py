"""File editor API — read, write, stat for in-browser editing."""
from __future__ import annotations

import mimetypes
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

from maggy.api.auth import check_auth

router = APIRouter(prefix="/api/editor", tags=["editor"])

_MAX_FILE_SIZE = 1_048_576  # 1 MB

_BLOCKED_PATHS = {
    "/etc", "/var/run", "/var/log", "/usr", "/bin", "/sbin",
    "/System", "/Library",
    "/private/etc", "/private/var",
    "/proc", "/sys", "/dev",
}

_ALLOWED_DOTDIRS = {".claude", ".maggy", ".config", ".local"}

_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".exe", ".dll", ".so", ".dylib", ".o", ".a",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".pyc", ".pyo", ".class", ".jar",
    ".sqlite", ".db", ".sqlite3",
}

_LANG_MAP = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".jsx": "javascript",
    ".json": "json", ".jsonl": "json",
    ".md": "markdown", ".mdx": "markdown",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp",
    ".cs": "csharp",
    ".xml": "xml", ".svg": "xml",
    ".txt": "plaintext",
    ".ini": "ini", ".cfg": "ini",
    ".env": "shell",
    ".dockerfile": "dockerfile",
    ".tf": "hcl",
    ".graphql": "graphql", ".gql": "graphql",
}


def _validate_path(raw: str, cwd: str | None = None) -> Path:
    """Resolve and validate a file path. Raises HTTPException on violation."""
    expanded = os.path.expanduser(raw)
    if not os.path.isabs(expanded):
        base = cwd or os.path.expanduser("~")
        expanded = os.path.normpath(os.path.join(base, expanded))
    resolved = Path(expanded).resolve()

    resolved_str = str(resolved)
    for blocked in _BLOCKED_PATHS:
        if resolved_str.startswith(blocked):
            raise HTTPException(403, f"Access denied: {blocked}")

    home = Path.home()
    if resolved.parent == home and resolved.name.startswith("."):
        if resolved.name not in _ALLOWED_DOTDIRS:
            raise HTTPException(403, f"Access denied: ~/{resolved.name}")

    return resolved


def _is_binary(path: Path) -> bool:
    """Check if file is binary by extension or content sniffing."""
    if path.suffix.lower() in _BINARY_EXTENSIONS:
        return True
    try:
        chunk = path.read_bytes()[:8192]
        return b"\x00" in chunk
    except Exception:
        return True


def _infer_language(path: Path) -> str:
    """Infer language from file extension."""
    ext = path.suffix.lower()
    if ext in _LANG_MAP:
        return _LANG_MAP[ext]
    name = path.name.lower()
    if name == "dockerfile":
        return "dockerfile"
    if name == "makefile":
        return "makefile"
    if name in (".gitignore", ".dockerignore", ".eslintignore"):
        return "gitignore"
    return "plaintext"


class ReadResponse(BaseModel):
    content: str | None = None
    size: int
    language: str = "plaintext"
    binary: bool = False
    too_large: bool = False
    mime: str | None = None


class WriteRequest(BaseModel):
    path: str
    content: str


class WriteResponse(BaseModel):
    ok: bool
    size: int
    path: str


class StatResponse(BaseModel):
    exists: bool
    is_file: bool = False
    is_dir: bool = False
    size: int = 0
    modified: str | None = None
    binary: bool = False


@router.get("/read")
async def read_file(
    request: Request,
    path: str = Query(...),
    cwd: str | None = Query(None),
    x_api_key: str | None = Header(None),
) -> ReadResponse:
    """Read a file for the in-browser editor."""
    check_auth(request, x_api_key)
    resolved = _validate_path(path, cwd)

    if not resolved.exists():
        raise HTTPException(404, f"File not found: {path}")
    if not resolved.is_file():
        raise HTTPException(400, f"Not a file: {path}")

    size = resolved.stat().st_size
    mime_type = mimetypes.guess_type(str(resolved))[0]

    if _is_binary(resolved):
        return ReadResponse(
            size=size, binary=True,
            mime=mime_type, language="binary",
        )

    if size > _MAX_FILE_SIZE:
        return ReadResponse(
            size=size, too_large=True,
            language=_infer_language(resolved),
        )

    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ReadResponse(size=size, binary=True, mime=mime_type)

    return ReadResponse(
        content=content, size=size,
        language=_infer_language(resolved),
    )


@router.post("/write")
async def write_file(
    request: Request,
    body: WriteRequest,
    x_api_key: str | None = Header(None),
) -> WriteResponse:
    """Write/save a file from the in-browser editor."""
    check_auth(request, x_api_key)
    resolved = _validate_path(body.path)

    content_bytes = body.content.encode("utf-8")
    if len(content_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(413, "File too large (1 MB max)")

    resolved.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: write to temp, then rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(resolved.parent),
        prefix=f".{resolved.name}.",
        suffix=".tmp",
    )
    closed = False
    try:
        os.write(fd, content_bytes)
        os.close(fd)
        closed = True
        os.rename(tmp_path, str(resolved))
    except Exception:
        if not closed:
            try:
                os.close(fd)
            except OSError:
                pass
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return WriteResponse(
        ok=True, size=len(content_bytes), path=str(resolved),
    )


@router.get("/stat")
async def stat_file(
    request: Request,
    path: str = Query(...),
    cwd: str | None = Query(None),
    x_api_key: str | None = Header(None),
) -> StatResponse:
    """Stat a file or directory."""
    check_auth(request, x_api_key)
    resolved = _validate_path(path, cwd)

    if not resolved.exists():
        return StatResponse(exists=False)

    st = resolved.stat()
    modified = datetime.fromtimestamp(
        st.st_mtime, tz=timezone.utc,
    ).isoformat()

    return StatResponse(
        exists=True,
        is_file=resolved.is_file(),
        is_dir=resolved.is_dir(),
        size=st.st_size,
        modified=modified,
        binary=_is_binary(resolved) if resolved.is_file() else False,
    )
