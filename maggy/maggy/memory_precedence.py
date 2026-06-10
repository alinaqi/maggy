"""Memory precedence — the reconciliation rule between Maggy's memory systems.

Maggy keeps three separately-evolving models of "what the system knows":
  - cikg    — the intent graph: WHY code exists, contracts, drift. Authoritative
              on intent/why and the invariants a change must preserve.
  - mnemos  — the typed memory graph: goals, decisions, handoffs (goals never
              evicted). Authoritative on what the team/user decided to do.
  - history — Claude-transcript ingest + haziness scoring. OBSERVATIONAL only:
              signals about past sessions, never authoritative on intent/goals.

Council finding T4 asked: when these disagree, which one does the executor gate
trust? This module is the answer — an explicit, ordered precedence. On a direct
conflict about a single fact, the highest-precedence source present wins;
`history` is advisory and never overrides cikg/mnemos.
"""

from __future__ import annotations

from typing import Any

# Highest precedence first. cikg (intent/contracts) > mnemos (goals/decisions)
# > history (observational signals).
PRECEDENCE: list[str] = ["cikg", "mnemos", "history"]

# Sources that are advisory only — they inform but never override.
ADVISORY: frozenset[str] = frozenset({"history"})


def rank(source: str) -> int:
    """Lower is stronger. Unknown sources rank below all known ones."""
    return PRECEDENCE.index(source) if source in PRECEDENCE else len(PRECEDENCE)


def winner(sources: list[str]) -> str | None:
    """The highest-precedence source among those present."""
    if not sources:
        return None
    return min(sources, key=rank)


def resolve(claims: dict[str, Any]) -> Any:
    """Return the value from the highest-precedence source in `claims`.

    `claims` maps source -> that source's value for the same fact. Advisory
    sources only win if no authoritative source has a claim.
    """
    if not claims:
        return None
    authoritative = {s: v for s, v in claims.items() if s not in ADVISORY}
    pool = authoritative or claims
    return pool[winner(list(pool))]


def is_authoritative(source: str) -> bool:
    """True if a source can override others (not advisory)."""
    return source not in ADVISORY
