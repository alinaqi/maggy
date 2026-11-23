"""Budget ledger: reservations against per_day_usd in one SQLite transaction (RFC §2.6.4)."""

from __future__ import annotations

import threading
from concurrent.futures import ProcessPoolExecutor

import pytest

from maggy.worker.ledger import BudgetLedger, BudgetRefused
from worker_supervisor_helpers import reserve_many


def test_reserve_within_cap_then_refuse_over_cap(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db", per_day_usd=1.0)
    ledger.reserve("a", 0.6)
    with pytest.raises(BudgetRefused, match="per_day_usd"):
        ledger.reserve("b", 0.5)
    assert ledger.spent_today() == pytest.approx(0.6)


def test_settle_replaces_reservation_with_actual(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db", per_day_usd=1.0)
    ledger.reserve("a", 0.9)
    ledger.settle("a", 0.2)
    assert ledger.spent_today() == pytest.approx(0.2)
    ledger.reserve("b", 0.8)
    assert ledger.spent_today() == pytest.approx(1.0)


def test_release_frees_the_reservation(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db", per_day_usd=1.0)
    ledger.reserve("a", 1.0)
    ledger.release("a")
    assert ledger.spent_today() == 0.0
    ledger.reserve("b", 1.0)


def test_settle_or_release_needs_an_open_reservation(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db", per_day_usd=1.0)
    with pytest.raises(KeyError):
        ledger.settle("missing", 0.1)
    ledger.reserve("a", 0.1)
    ledger.settle("a", 0.1)
    with pytest.raises(KeyError):
        ledger.release("a")


def test_duplicate_run_id_and_negative_amount_rejected(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db", per_day_usd=1.0)
    ledger.reserve("a", 0.1)
    with pytest.raises(ValueError, match="already"):
        ledger.reserve("a", 0.1)
    with pytest.raises(ValueError):
        ledger.reserve("b", -1.0)


def test_no_daily_cap_still_records(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db")
    ledger.reserve("a", 50.0)
    assert ledger.spent_today() == 50.0


def test_default_path_is_under_maggy_home(tmp_path):
    ledger = BudgetLedger()
    ledger.reserve("a", 0.0)
    assert ledger.path.name == "budget.db" and ledger.path.parent.name == ".maggy"


def test_concurrent_threads_never_exceed_cap(tmp_path):
    db = tmp_path / "budget.db"
    granted: list[str] = []

    def attempt(n: int) -> None:
        try:
            BudgetLedger(db, per_day_usd=1.0).reserve(f"t{n}", 0.1)
            granted.append(f"t{n}")
        except BudgetRefused:
            pass

    threads = [threading.Thread(target=attempt, args=(n,)) for n in range(40)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(granted) == 10
    assert BudgetLedger(db).spent_today() == pytest.approx(1.0)


def test_concurrent_processes_never_exceed_cap(tmp_path):
    db = str(tmp_path / "budget.db")
    with ProcessPoolExecutor(max_workers=4) as pool:
        granted = sum(pool.map(reserve_many, [(db, 10, 0.07)] * 4))
    assert granted == 14
    assert BudgetLedger(tmp_path / "budget.db").spent_today() <= 1.0
