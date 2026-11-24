"""Tests for per-project routing profiles (private per-machine config)."""

from __future__ import annotations


class TestProfilePath:
    def test_encode_slashes_to_dashes(self):
        from maggy.project_routing import encode_project_path
        assert encode_project_path("/Users/x/proj") == "-Users-x-proj"

    def test_path_under_base(self, tmp_path):
        from maggy.project_routing import project_profile_path
        p = project_profile_path("/Users/x/proj", base=tmp_path)
        assert p == tmp_path / "-Users-x-proj" / "routing.yaml"


class TestLoadSave:
    def test_missing_returns_none(self, tmp_path):
        from maggy.project_routing import load_project_profile
        assert load_project_profile("/no/such/proj", base=tmp_path) is None

    def test_roundtrip(self, tmp_path):
        from maggy.project_routing import (
            ProjectProfile, save_project_profile, load_project_profile,
        )
        prof = ProjectProfile(
            profile="simple", default_provider="glm", default_model="glm-5.2",
            escalate_paths={"**/auth/**": "claude"},
        )
        save_project_profile(prof, "/Users/x/proj", base=tmp_path)
        got = load_project_profile("/Users/x/proj", base=tmp_path)
        assert got is not None
        assert got.profile == "simple"
        assert got.default_model == "glm-5.2"
        assert got.escalate_paths == {"**/auth/**": "claude"}

