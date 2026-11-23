"""Budgeted runs: reserve before launch, settle or release after (RFC §2.6.4)."""

from __future__ import annotations

import sys

import pytest

from maggy.harness.schema_sections import Budget
from maggy.worker.budgeted import cost_limit_usd, reservation_usd, run_budgeted
from maggy.worker.launch import Refused
from maggy.worker.ledger import BudgetLedger, BudgetRefused
from worker_supervisor_helpers import cost_adapter as adapter
from worker_supervisor_helpers import job, marker_job


def test_streaming_adapter_reserves_per_run_and_is_capped_there():
    budget = Budget(per_run_usd=2.0, per_day_usd=10.0)
    assert reservation_usd(adapter(True, 0.5), budget) == 2.0
    assert cost_limit_usd(adapter(True, 0.5), budget) == 2.0


def test_non_streaming_adapter_reserves_fixed_and_has_no_stream_cap():
    budget = Budget(per_run_usd=2.0)
    assert reservation_usd(adapter(False, 0.5), budget) == 0.5
    assert reservation_usd(adapter(False, None), budget) == 2.0
    assert cost_limit_usd(adapter(False, 0.5), budget) is None


def test_no_reservable_amount_is_refused():
    with pytest.raises(Refused, match="per_run_usd"):
        reservation_usd(adapter(True, None), Budget())


def test_refused_reservation_prevents_launch(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db", per_day_usd=1.0)
    ledger.reserve("earlier", 0.9)
    with pytest.raises(BudgetRefused):
        run_budgeted(marker_job(tmp_path), ledger, 0.5)
    assert not (tmp_path / "ran.txt").exists()
    assert ledger.spent_today() == pytest.approx(0.9)


def test_success_settles_at_parsed_cost(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db", per_day_usd=1.0)
    code = "import json; print(json.dumps({'type':'result','total_cost_usd':0.1,'result':'ok'}))"
    run = run_budgeted(job(tmp_path, [sys.executable, "-c", code], parser="claude-json"),
                       ledger, 0.8)
    assert run.outcome == "succeeded"
    assert ledger.spent_today() == pytest.approx(0.1)


def test_unknown_cost_settles_at_the_reservation(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db", per_day_usd=1.0)
    run_budgeted(marker_job(tmp_path), ledger, 0.4)
    assert ledger.spent_today() == pytest.approx(0.4)


def test_launch_failure_releases_the_reservation(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db", per_day_usd=1.0)
    with pytest.raises(OSError):
        run_budgeted(job(tmp_path, [str(tmp_path / "missing-cli")]), ledger, 0.4)
    assert ledger.spent_today() == 0.0


def test_stop_file_skips_reservation_and_launch(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db", per_day_usd=1.0)
    (tmp_path / "STOP").write_text("")
    run = run_budgeted(marker_job(tmp_path), ledger, 0.4)
    assert run.reason == "stopped" and not run.launched
    assert ledger.spent_today() == 0.0


def test_crash_after_launch_settles_at_the_reservation(tmp_path, monkeypatch):
    ledger = BudgetLedger(tmp_path / "budget.db", per_day_usd=1.0)

    def boom(*_args):
        raise RuntimeError("watch crashed")

    monkeypatch.setattr("maggy.worker.supervisor._watch", boom)
    with pytest.raises(RuntimeError):
        run_budgeted(marker_job(tmp_path, sleep_s=60), ledger, 0.4)
    assert ledger.spent_today() == pytest.approx(0.4)
