"""Tests for council config loading and validation."""


class TestCouncilConfigLoad:
    def test_load_default_config(self):
        from maggy.services.council_config import load_council_config
        cfg = load_council_config()
        assert cfg.enabled is True
        assert cfg.threshold >= 1

    def test_config_has_reviewers(self):
        from maggy.services.council_config import load_council_config
        cfg = load_council_config()
        assert len(cfg.reviewers) > 0
        assert "plan" in cfg.reviewers
        assert "review" in cfg.reviewers

    def test_config_has_models(self):
        from maggy.services.council_config import load_council_config
        cfg = load_council_config()
        assert len(cfg.models) >= 10

    def test_model_has_required_fields(self):
        from maggy.services.council_config import load_council_config
        cfg = load_council_config()
        for m in cfg.models:
            assert m.id
            assert m.label
            assert isinstance(m.tier, int)

    def test_threshold_clamped(self):
        from maggy.services.council_config import CouncilConfig
        cfg = CouncilConfig(threshold=99)
        assert cfg.effective_threshold(3) == 3
        cfg2 = CouncilConfig(threshold=0)
        assert cfg2.effective_threshold(3) == 1

    def test_reviewers_for_context(self):
        from maggy.services.council_config import load_council_config
        cfg = load_council_config()
        plan_reviewers = cfg.get_reviewers("plan")
        assert len(plan_reviewers) >= 1
        for r in plan_reviewers:
            assert r.id
            assert r.enabled is True or r.enabled is False

    def test_unknown_context_returns_empty(self):
        from maggy.services.council_config import load_council_config
        cfg = load_council_config()
        assert cfg.get_reviewers("nonexistent") == []

    def test_to_dict_roundtrip(self):
        from maggy.services.council_config import load_council_config
        cfg = load_council_config()
        d = cfg.to_dict()
        assert "enabled" in d
        assert "threshold" in d
        assert "models" in d
        assert "reviewers" in d


class TestCouncilChief:
    def test_default_chief_is_fable5(self, tmp_path):
        from maggy.services.council_config import load_council_config
        cfg = load_council_config(tmp_path / "nope.yaml")  # missing -> defaults
        assert cfg.chief == "claude-fable-5"

    def test_chief_is_lead_reviewer_in_every_context(self, tmp_path):
        from maggy.services.council_config import load_council_config
        cfg = load_council_config(tmp_path / "nope.yaml")
        for ctx in ("plan", "review", "architecture"):
            assert cfg.get_reviewers(ctx)[0].id == "claude-fable-5"

    def test_get_chief_resolves_to_model(self, tmp_path):
        from maggy.services.council_config import load_council_config
        cfg = load_council_config(tmp_path / "nope.yaml")
        chief = cfg.get_chief()
        assert chief is not None
        assert chief.id == "claude-fable-5"
        assert chief.cmd_argv()[0].endswith("/claude-fable-5")

    def test_chief_round_trips(self, tmp_path):
        from maggy.services.council_config import (
            load_council_config,
            save_council_config,
        )
        p = tmp_path / "council.yaml"
        cfg = load_council_config(tmp_path / "nope.yaml")
        cfg.chief = "claude-opus"
        save_council_config(cfg, p)
        assert load_council_config(p).chief == "claude-opus"
