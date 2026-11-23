"""The FP-filter config must come from the trusted base branch, not the PR under review."""

from __future__ import annotations

import pytest

from maggy.review.models import Finding, Severity
from maggy.review.fp_filter import FPFilterRun
from maggy.review.pipeline import deterministic_fp_filter
from maggy.review.repo_config import CONFIG_PATH, load_review_config
from fp_filter_helpers import make_repo as _repo
from fp_filter_helpers import publish_base
from fp_filter_helpers import write as _write

SQLI = "SQL injection executed unconditionally"


def _sqli():
    return Finding(file="src/db/query.py", severity=Severity.blocking, title=SQLI, detail="d")


def _filter(root, base_ref="main"):
    return deterministic_fp_filter([_sqli()], FPFilterRun(str(root), lambda _m: None, base_ref))


def test_config_added_only_by_pr_head_is_ignored(tmp_path):
    _write(tmp_path, "README.md", "hello")
    publish_base(tmp_path, "README.md")
    _write(tmp_path, CONFIG_PATH, "router_files: [README.md]\n")
    kept, dropped = _filter(tmp_path)
    assert dropped == 0 and kept == [_sqli()]


def test_pr_head_cannot_rewrite_base_config(tmp_path):
    _repo(tmp_path)
    publish_base(tmp_path)
    _write(tmp_path, CONFIG_PATH, "router_files: [README.md]\n")
    _write(tmp_path, "README.md", "hello")
    cfg = load_review_config(tmp_path, "main")
    assert cfg is not None and cfg.router_files == ["src/Router.tsx"]


def test_no_base_ref_means_no_filter(tmp_path):
    _write(tmp_path, CONFIG_PATH, "router_files: [README.md]\n")
    _write(tmp_path, "README.md", "hello")
    publish_base(tmp_path, ".")
    kept, dropped = _filter(tmp_path, base_ref=None)
    assert dropped == 0 and kept == [_sqli()]


@pytest.mark.parametrize("bad", ["/etc/hosts", "../outside.tsx", "src/../../x.tsx", "C:/x"])
@pytest.mark.parametrize("key", ["router_files", "translation_locales"])
def test_paths_outside_repo_are_rejected(tmp_path, key, bad):
    _write(tmp_path, CONFIG_PATH, f"{key}: ['{bad}']\n")
    publish_base(tmp_path)
    assert load_review_config(tmp_path, "main") is None
