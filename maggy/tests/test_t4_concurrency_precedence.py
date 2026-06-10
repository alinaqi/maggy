"""Tests for T4 — SQLite concurrency hardening + memory precedence."""

from __future__ import annotations

import sqlite3
import threading


from maggy.memory_precedence import (
    is_authoritative,
    resolve,
    winner,
)


# ── Part 2: busy_timeout on the concurrent multi-agent stores ──────────

def _busy_timeout(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA busy_timeout").fetchone()[0]


def test_polyphony_store_sets_busy_timeout(tmp_path):
    from maggy.orchestrator.store import PolyphonyStore
    store = PolyphonyStore(tmp_path)
    store.init_db()
    conn = store._connect()
    try:
        assert _busy_timeout(conn) >= 5000
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_concurrent_writers_wait_not_error(tmp_path):
    """With busy_timeout, a second writer waits instead of raising 'locked'."""
    db = str(tmp_path / "t.db")

    def _open():
        c = sqlite3.connect(db, timeout=0)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=5000")
        return c

    a = _open()
    a.execute("CREATE TABLE t(x)")
    a.commit()
    a.execute("BEGIN IMMEDIATE")  # hold a write lock
    a.execute("INSERT INTO t VALUES (1)")

    errors = []

    def writer():
        b = _open()
        try:
            b.execute("INSERT INTO t VALUES (2)")  # would block, then succeed
            b.commit()
        except sqlite3.OperationalError as e:
            errors.append(str(e))
        finally:
            b.close()

    th = threading.Thread(target=writer)
    th.start()
    a.commit()  # release the lock so the waiting writer proceeds
    th.join(timeout=10)
    assert errors == []  # busy_timeout let it wait, not fail
    a.close()


# ── Part 1: memory precedence ──────────────────────────────────────────

def test_precedence_order_cikg_over_mnemos_over_history():
    assert winner(["history", "mnemos", "cikg"]) == "cikg"
    assert winner(["history", "mnemos"]) == "mnemos"
    assert winner(["history"]) == "history"
    assert winner([]) is None


def test_resolve_picks_highest_authoritative():
    claims = {"history": "old", "mnemos": "goal-A", "cikg": "intent-X"}
    assert resolve(claims) == "intent-X"


def test_history_is_advisory_only():
    assert is_authoritative("history") is False
    assert is_authoritative("cikg") is True
    # history alone wins only when no authoritative source has a claim
    assert resolve({"history": "signal"}) == "signal"
    # but never overrides an authoritative source
    assert resolve({"history": "signal", "mnemos": "decision"}) == "decision"


def test_unknown_source_ranks_last():
    assert winner(["unknown", "mnemos"]) == "mnemos"
