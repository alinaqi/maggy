"""3-level terminology map for intent normalization.

Level 1: Canonical terms (e.g., "deploy")
Level 2: Synonyms (e.g., "ship", "push", "release")
Level 3: Project-specific aliases (learned over time)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TermEntry:
    """A canonical term with synonyms."""

    canonical: str
    synonyms: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


DEFAULT_TERMS: list[TermEntry] = [
    TermEntry("deploy", ["ship", "push", "release", "publish"]),
    TermEntry("test", ["check", "verify", "validate", "qa"]),
    TermEntry("fix", ["repair", "patch", "resolve", "debug"]),
    TermEntry("create", ["add", "build", "make", "generate"]),
    TermEntry("delete", ["remove", "drop", "destroy", "clean"]),
    TermEntry("update", ["modify", "change", "edit", "revise"]),
    TermEntry("search", ["find", "lookup", "query", "locate"]),
    TermEntry("review", ["inspect", "audit", "examine", "check"]),
]


class TerminologyMap:
    """Three-level terminology resolution."""

    def __init__(
        self, terms: list[TermEntry] | None = None,
    ):
        # Deep copy to avoid mutating module-level defaults
        if terms is not None:
            self._terms = terms
        else:
            self._terms = [
                TermEntry(
                    t.canonical,
                    list(t.synonyms),
                    list(t.aliases),
                )
                for t in DEFAULT_TERMS
            ]
        self._index = self._build_index()

    def _build_index(self) -> dict[str, str]:
        idx: dict[str, str] = {}
        for t in self._terms:
            idx[t.canonical] = t.canonical
            for s in t.synonyms:
                idx[s] = t.canonical
            for a in t.aliases:
                idx[a] = t.canonical
        return idx

    def resolve(self, word: str) -> str | None:
        """Resolve a word to its canonical form."""
        return self._index.get(word.lower())

    def add_alias(self, canonical: str, alias: str) -> bool:
        """Add a project-specific alias (Level 3)."""
        for t in self._terms:
            if t.canonical == canonical:
                t.aliases.append(alias.lower())
                self._index[alias.lower()] = canonical
                return True
        return False

    def list_terms(self) -> list[TermEntry]:
        return list(self._terms)
