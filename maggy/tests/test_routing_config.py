"""Tests for routing config — stakes patterns, cascade policy, YAML roundtrip."""

from __future__ import annotations

from pathlib import Path

import yaml

from maggy.routing_rules import CascadePolicy
from maggy.routing_rules_defaults import default_rules
from maggy.routing_rules_io import load, save, to_dict


class TestStakesPatterns:
    def test_default_has_high_patterns(self):
        rules = default_rules()
        assert "auth" in rules.stakes.high.file_patterns
        assert "security" in rules.stakes.high.task_types

    def test_default_has_medium_patterns(self):
        rules = default_rules()
        assert "api" in rules.stakes.medium.file_patterns
        assert "feature" in rules.stakes.medium.task_types

    def test_default_low_has_empty_patterns(self):
        rules = default_rules()
        assert rules.stakes.low.file_patterns == []


class TestCascadePolicy:
    def test_defaults(self):
        policy = CascadePolicy()
        assert policy.enabled is True
        assert policy.min_blast == 5
        assert policy.min_stakes == "medium"
        assert policy.max_attempts == 3
        assert policy.quality_threshold == 3

    def test_custom_values(self):
        policy = CascadePolicy(
            enabled=False, min_blast=3,
            min_stakes="low", max_attempts=5,
        )
        assert policy.enabled is False
        assert policy.min_blast == 3


class TestYamlRoundtrip:
    def test_roundtrip_preserves_stakes(self, tmp_path: Path):
        rules = default_rules()
        rules.stakes.high.file_patterns.append("custom_critical")
        save(rules, tmp_path / "rules.yaml")
        loaded = load(tmp_path / "rules.yaml")
        assert "custom_critical" in loaded.stakes.high.file_patterns

    def test_roundtrip_preserves_cascade(self, tmp_path: Path):
        rules = default_rules()
        rules.cascade.min_blast = 7
        save(rules, tmp_path / "rules.yaml")
        loaded = load(tmp_path / "rules.yaml")
        assert loaded.cascade.min_blast == 7

    def test_roundtrip_preserves_conventions(self, tmp_path: Path):
        rules = default_rules()
        save(rules, tmp_path / "rules.yaml")
        loaded = load(tmp_path / "rules.yaml")
        assert len(loaded.conventions) == len(rules.conventions)

    def test_user_edits_preserved(self, tmp_path: Path):
        """Write, manually edit YAML, reload — edits survive."""
        rules = default_rules()
        path = tmp_path / "rules.yaml"
        save(rules, path)
        data = yaml.safe_load(path.read_text())
        data["cascade_policy"]["min_blast"] = 2
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        loaded = load(path)
        assert loaded.cascade.min_blast == 2

    def test_missing_file_seeds_defaults(self, tmp_path: Path):
        loaded = load(tmp_path / "nonexistent.yaml")
        assert loaded.version == 1
        assert loaded.cascade.enabled is True
        assert "auth" in loaded.stakes.high.file_patterns


class TestToDict:
    def test_stakes_in_output(self):
        rules = default_rules()
        d = to_dict(rules)
        assert "stakes_patterns" in d
        assert "high" in d["stakes_patterns"]

    def test_cascade_in_output(self):
        rules = default_rules()
        d = to_dict(rules)
        assert "cascade_policy" in d
        assert d["cascade_policy"]["enabled"] is True
