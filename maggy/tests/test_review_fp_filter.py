"""Deterministic FP filter is driven by a per-repo .maggy/review.yaml (no hardcoded paths).

The config is trusted only from the base branch (origin/<base>), never the PR head.
"""

from __future__ import annotations

import pytest

from fp_filter_helpers import (FLAG, GENERIC_CONFIG, I18N, LEGACY_LAYOUT, blocking, make_repo,
                               publish_base, run_filter, write)
from maggy.review.fp_filter import FPFilterRun
from maggy.review.pipeline import deterministic_fp_filter
from maggy.review.repo_config import RepoReviewConfig, load_review_config


class TestNoConfig:
    def test_findings_pass_through_unchanged(self, tmp_path):
        make_repo(tmp_path, config=None)
        findings = [blocking("src/Widget.tsx", I18N), blocking("src/Widget.tsx", FLAG)]
        kept, dropped = run_filter(tmp_path, findings)
        assert dropped == 0 and kept == findings

    def test_legacy_layout_without_config_is_not_special(self, tmp_path):
        make_repo(tmp_path, config=None, layout=LEGACY_LAYOUT)
        write(tmp_path, "src/Widget.tsx", "t('zenny.a')")
        findings = [blocking("src/Widget.tsx", I18N), blocking("src/Widget.tsx", FLAG)]
        kept, dropped = run_filter(tmp_path, findings)
        assert dropped == 0 and kept == findings

    def test_no_local_path(self):
        findings = [blocking("a.tsx", I18N)]
        assert deterministic_fp_filter(findings, FPFilterRun(None, lambda _m: None)) == (findings, 0)


class TestConfigLoading:
    def test_missing_file_returns_none(self, tmp_path):
        publish_base(tmp_path, ".")
        assert load_review_config(tmp_path, "main") is None

    def test_parses_keys(self, tmp_path):
        write(tmp_path, ".maggy/review.yaml", GENERIC_CONFIG)
        publish_base(tmp_path)
        cfg = load_review_config(tmp_path, "main")
        assert cfg == RepoReviewConfig(translation_locales=["locales/en.json", "locales/de.json"],
                                       translation_key_prefix="app.", router_files=["src/Router.tsx"])

    @pytest.mark.parametrize("text", ["::not yaml: [", "- a list\n", "translation_locales: 5\n"])
    def test_invalid_config_is_ignored(self, tmp_path, text):
        write(tmp_path, ".maggy/review.yaml", text)
        publish_base(tmp_path)
        assert load_review_config(tmp_path, "main") is None
