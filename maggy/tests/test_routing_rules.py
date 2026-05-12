"""Tests for routing rules — load, save, apply, learn."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.routing_rules import (
    ModelOverride,
    PerformanceRecord,
    RoutingRules,
    apply_override,
    learn_override,
    record_outcome,
)
from maggy.routing_rules_defaults import default_rules
from maggy.routing_rules_io import load, save


@pytest.fixture()
def rules_path(tmp_path: Path) -> Path:
    return tmp_path / "routing-rules.yaml"


class TestDefaultRules:
    def test_seeds_task_type_overrides(self):
        rules = default_rules()
        assert "docs" in rules.task_type_overrides
        assert "security" in rules.task_type_overrides
        assert "tests" in rules.task_type_overrides

    def test_seeds_pipeline_phases(self):
        rules = default_rules()
        assert "spec" in rules.pipeline_phases
        assert "tdd_red" in rules.pipeline_phases
        assert rules.pipeline_phases["tdd_green"].model == "auto"

    def test_seeds_model_performance(self):
        rules = default_rules()
        assert "claude" in rules.model_performance
        assert "local" in rules.model_performance


class TestLoadSave:
    def test_load_creates_default(self, rules_path: Path):
        rules = load(rules_path)
        assert rules_path.exists()
        assert "docs" in rules.task_type_overrides

    def test_roundtrip(self, rules_path: Path):
        original = default_rules()
        save(original, rules_path)
        loaded = load(rules_path)
        assert loaded.version == original.version
        assert set(loaded.task_type_overrides) == set(
            original.task_type_overrides,
        )

    def test_load_existing(self, rules_path: Path):
        save(default_rules(), rules_path)
        rules = load(rules_path)
        assert rules.task_type_overrides["security"].model == "claude"


class TestApplyOverride:
    def test_phase_takes_priority(self):
        rules = default_rules()
        result = apply_override(rules, "feature", "spec")
        assert result == "claude"

    def test_auto_phase_returns_none(self):
        rules = default_rules()
        result = apply_override(rules, "feature", "tdd_green")
        assert result is None

    def test_task_type_override(self):
        rules = default_rules()
        result = apply_override(rules, "security")
        assert result == "claude"

    def test_no_override_returns_none(self):
        rules = default_rules()
        result = apply_override(rules, "feature")
        assert result is None

    def test_low_confidence_ignored(self):
        rules = RoutingRules(
            task_type_overrides={
                "test": ModelOverride("kimi", "weak", 0.3),
            },
        )
        result = apply_override(rules, "test")
        assert result is None


class TestRecordOutcome:
    def test_updates_success_rate(self, rules_path: Path):
        rules = default_rules()
        record_outcome(rules, "claude", "feature", True, rules_path)
        perf = rules.model_performance["claude"]
        assert perf.tasks_completed == 7
        assert perf.success_rate > 0.9

    def test_creates_new_model(self, rules_path: Path):
        rules = default_rules()
        record_outcome(rules, "gemini", "feature", True, rules_path)
        assert "gemini" in rules.model_performance
        assert rules.model_performance["gemini"].success_rate == 1.0

    def test_records_failure(self, rules_path: Path):
        rules = RoutingRules(
            model_performance={
                "test": PerformanceRecord(
                    tasks_completed=1, success_rate=1.0,
                ),
            },
        )
        record_outcome(rules, "test", "security", False, rules_path)
        assert rules.model_performance["test"].success_rate == 0.5
        assert "security" in rules.model_performance["test"].weaknesses


class TestLearnOverride:
    def test_adds_new_override(self, rules_path: Path):
        rules = default_rules()
        learn_override(
            rules, "frontend", "claude",
            "Codex too slow for frontend (280s vs 122s)",
            0.8, rules_path,
        )
        assert rules.task_type_overrides["frontend"].model == "claude"
        assert rules.task_type_overrides["frontend"].source == "learned"

    def test_persists_to_disk(self, rules_path: Path):
        rules = default_rules()
        save(rules, rules_path)
        learn_override(
            rules, "frontend", "claude", "test", 0.9, rules_path,
        )
        reloaded = load(rules_path)
        assert "frontend" in reloaded.task_type_overrides
