"""Extensible language registry for the council reviewer.

A *language* is: a name, the file extensions (and path markers) that map files
to it, a skill file (review knowledge injected into the agents), and — for the
future — an optional static-lint hook. The reviewer is language-agnostic; what
makes it understand Python vs Go is purely the registry entry + the skill file.

Adding a language needs NO core code change. Either:
  1. drop ``skills/<name>.md`` and call ``register_language(Language(...))``, or
  2. declare it in Maggy config under ``review.languages`` (loaded at runtime by
     ``load_from_config``).

This is the seam the rest of the pipeline detects + loads skills through.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"


@dataclass(frozen=True)
class Language:
    """One reviewable language and how to recognize + teach it."""

    name: str
    extensions: tuple[str, ...] = ()
    # substrings that, if present in a path, imply this language regardless of
    # extension (e.g. "/migrations/" -> db even for a .py migration).
    path_markers: tuple[str, ...] = ()
    # skill filename under skills/; defaults to "<name>.md".
    skill_file: str = ""

    def skill_path(self, skills_dir: Path = SKILLS_DIR) -> Path:
        return skills_dir / (self.skill_file or f"{self.name}.md")


# Built-in roster. python/typescript/db carry over from revir; the rest are the
# seeded "common set" — each is just an entry + a skills/<name>.md file.
_BUILTINS = (
    Language("python", (".py",)),
    Language("typescript", (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")),
    Language("db", (".sql",), path_markers=("alembic", "migrations/", "migrations-")),
    Language("go", (".go",)),
    Language("rust", (".rs",)),
    Language("java", (".java",)),
    Language("csharp", (".cs",)),
    Language("ruby", (".rb",)),
    Language("php", (".php",)),
)

REGISTRY: dict[str, Language] = {lang.name: lang for lang in _BUILTINS}


def register_language(lang: Language) -> None:
    """Add (or replace) a language in the registry."""
    REGISTRY[lang.name] = lang


def supported() -> list[str]:
    """Names of all registered languages, sorted."""
    return sorted(REGISTRY)


def detect_languages(filenames) -> list[str]:
    """Languages present in a set of changed file paths (registry-driven)."""
    found: set[str] = set()
    for fn in filenames:
        low = fn.lower()
        for lang in REGISTRY.values():
            if any(low.endswith(e) for e in lang.extensions) or any(m in low for m in lang.path_markers):
                found.add(lang.name)
    return sorted(found)


def load_skill(languages, skills_dir: Path = SKILLS_DIR) -> str:
    """base skill + the per-language skill for each language the PR touches.

    Unknown language names are skipped silently (their skill file just may not
    exist yet) — the base skill always loads so a review is never skill-less.
    """
    parts: list[str] = []
    base = skills_dir / "base.md"
    if base.exists():
        parts.append(base.read_text())
    for name in languages:
        lang = REGISTRY.get(name)
        path = lang.skill_path(skills_dir) if lang else skills_dir / f"{name}.md"
        if path.exists():
            parts.append(path.read_text())
    return "\n\n".join(parts)


def load_from_config(entries) -> list[str]:
    """Register user-defined languages from Maggy config (``review.languages``).

    Each entry is a dict: ``{name, extensions:[...], path_markers?:[...],
    skill_file?}``. Returns the names registered. Malformed entries are skipped.
    """
    added: list[str] = []
    for e in entries or []:
        try:
            lang = Language(
                name=e["name"],
                extensions=tuple(e.get("extensions", ())),
                path_markers=tuple(e.get("path_markers", ())),
                skill_file=e.get("skill_file", ""),
            )
        except (KeyError, TypeError):
            continue
        register_language(lang)
        added.append(lang.name)
    return added
