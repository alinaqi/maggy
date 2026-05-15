"""Scope tag inference and comparison."""

from __future__ import annotations

from pathlib import PurePosixPath


def infer_scope_tags(file_path: str) -> list[str]:
    """Extract scope tags from a file path.

    e.g. 'src/auth/login.py' -> ['src', 'auth']
    """
    if not file_path:
        return []
    parts = PurePosixPath(file_path).parts
    # Exclude the filename itself, keep directory components
    dirs = [p for p in parts[:-1] if p != "/"]
    return dirs[:5]  # cap at 5 levels


def merge_scope_tags(
    existing: list[str], new: list[str],
) -> list[str]:
    """Deduplicated union of scope tags."""
    seen: set[str] = set()
    result: list[str] = []
    for tag in [*existing, *new]:
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def scope_overlap(
    tags_a: list[str], tags_b: list[str],
) -> float:
    """Jaccard similarity between two scope tag sets."""
    if not tags_a and not tags_b:
        return 1.0
    set_a = set(tags_a)
    set_b = set(tags_b)
    union = set_a | set_b
    if not union:
        return 1.0
    return len(set_a & set_b) / len(union)
