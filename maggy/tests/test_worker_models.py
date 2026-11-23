"""Worker spec/result models (RFC §2.3): validation and round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from maggy.worker.models import Blocker, CheckResult, WorkerResult, WorkerSpec


def _spec(**changes) -> dict:
    data = {
        "awg_ref": "AWG-7", "attempt_id": "att-1", "fencing_token": "f-9",
        "stage": "build", "repo": "/r", "base_commit": "abc123",
        "spec_version": 2, "workspace": "/w", "permission": "workspace",
        "deadline_s": 600, "budget_usd": 1.5, "prompt": "do {x} $(rm)",
    }
    data.update(changes)
    return data


def _check() -> dict:
    return {"name": "test", "command": "pytest -q", "exit_code": 0,
            "passed": True, "sha": "def456", "duration_s": 3.2,
            "log_path": "/logs/test.log"}


def _result(**changes) -> dict:
    data = {
        "outcome": "succeeded", "candidate_commit": "def456",
        "changed_files": ["a.py"], "checks": [_check()], "artifacts": [],
        "blocker": None, "cost_usd": 0.12, "elapsed_s": 40.0,
        "agent": "claude", "model": "sonnet", "adapter_version": "2.1.0",
    }
    data.update(changes)
    return data


def test_worker_spec_round_trips():
    spec = WorkerSpec.model_validate(_spec())
    assert spec.repo == Path("/r") and spec.prompt == "do {x} $(rm)"
    assert WorkerSpec.model_validate_json(spec.model_dump_json()) == spec


@pytest.mark.parametrize("change", [
    {"stage": "deploy-prod"}, {"deadline_s": 0}, {"budget_usd": -1},
    {"surprise": 1},
])
def test_worker_spec_rejects_bad_values(change):
    with pytest.raises(ValidationError):
        WorkerSpec.model_validate(_spec(**change))


def test_worker_result_round_trips_with_checks():
    result = WorkerResult.model_validate(_result())
    assert isinstance(result.checks[0], CheckResult)
    assert result.checks[0].log_path == Path("/logs/test.log")
    assert WorkerResult.model_validate_json(result.model_dump_json()) == result


def test_blocked_outcome_requires_a_blocker():
    with pytest.raises(ValidationError, match="blocker"):
        WorkerResult.model_validate(_result(outcome="blocked"))
    blocker = {"question": "Which DB?", "options": ["sqlite", "pg"]}
    result = WorkerResult.model_validate(_result(outcome="blocked", blocker=blocker))
    assert result.blocker == Blocker(question="Which DB?", options=["sqlite", "pg"])


@pytest.mark.parametrize("change", [
    {"outcome": "done"}, {"cost_usd": -0.1}, {"elapsed_s": -1},
])
def test_worker_result_rejects_bad_values(change):
    with pytest.raises(ValidationError):
        WorkerResult.model_validate(_result(**change))


def test_check_cannot_pass_with_nonzero_exit():
    with pytest.raises(ValidationError, match="exit_code"):
        CheckResult.model_validate({**_check(), "exit_code": 1})
