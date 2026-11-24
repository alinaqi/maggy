"""Guard: project_routing.decide_model is gone (harness profile tiers pick models)."""

from __future__ import annotations

import maggy.project_routing as project_routing


def test_decide_model_removed():
    assert not hasattr(project_routing, "decide_model")


def test_decide_model_only_helpers_removed():
    for name in ("TaskContext", "RouteChoice", "_security_target"):
        assert not hasattr(project_routing, name), name


def test_profile_api_kept():
    for name in ("ProjectProfile", "load_project_profile", "save_project_profile",
                 "project_profile_path", "encode_project_path"):
        assert hasattr(project_routing, name), name
