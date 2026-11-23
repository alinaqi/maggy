"""Budgeted worker runs: reserve, launch, then settle or release (RFC §2.6.4)."""

from __future__ import annotations

from maggy.harness.schema_sections import Budget
from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.job import Job, Supervised
from maggy.worker.launch import Refused
from maggy.worker.ledger import BudgetLedger
from maggy.worker.process_group import LaunchFailed
from maggy.worker.supervisor import supervise


def reservation_usd(adapter: AdapterSpec, budget: Budget) -> float:
    """Amount to reserve: per_run_usd for cost streamers, else the fixed reservation."""
    fixed = adapter.cost.fixed_reservation_usd
    order = (budget.per_run_usd, fixed) if adapter.cost.streams else (fixed, budget.per_run_usd)
    amount = next((value for value in order if value is not None), None)
    if amount is None:
        raise Refused(f"adapter {adapter.name}: set budget.per_run_usd (or the adapter's "
                      "cost.fixed_reservation_usd) so the run can be reserved")
    return amount


def cost_limit_usd(adapter: AdapterSpec, budget: Budget) -> float | None:
    """The live cost cap: only adapters that stream cost can be killed on overspend."""
    return budget.per_run_usd if adapter.cost.streams else None


def run_budgeted(job: Job, ledger: BudgetLedger, amount: float) -> Supervised:
    """Reserve (BudgetRefused stops launch), supervise, then settle (unknown cost: reserved)."""
    if job.stop_file.exists():
        return supervise(job)
    ledger.reserve(job.run_id, amount)
    try:
        run = supervise(job)
    except LaunchFailed:
        ledger.release(job.run_id)
        raise
    except BaseException:
        ledger.settle(job.run_id, amount)  # crashed after launch: assume the worst
        raise
    if run.launched:
        ledger.settle(job.run_id, amount if run.cost_usd is None else run.cost_usd)
    else:
        ledger.release(job.run_id)
    return run
