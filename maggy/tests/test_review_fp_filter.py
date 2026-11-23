"""Deterministic FP filter is driven by a per-repo .maggy/review.yaml (no hardcoded paths).

The config is trusted only from the base branch (origin/<base>), never the PR head.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from maggy.review.models import Finding, Severity
from maggy.review.pipeline import deterministic_fp_filter
from maggy.review.repo_config import CONFIG_PATH, RepoReviewConfig, load_review_config

GENERIC_CONFIG = """\
translation_locales:
  - locales/en.json
  - locales/de.json
translation_key_prefix: app.
router_files:
  - src/Router.tsx
"""

# The pre-change hardcoded values, now expressed as a per-repo fixture config.
LEGACY_CONFIG = """\
translation_locales:
  - libs/shared/services/translate/src/lib/locals/en/en.json
  - libs/shared/services/translate/src/lib/locals/de/de.json
translation_key_prefix: zenny.
router_files:
  - apps/platform-app/src/Router.tsx
"""

LOCALE = {"app": {"title": "T", "items_one": "1", "items_other": "n"}}


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


GENERIC_LAYOUT = ("locales/en.json", "locales/de.json", "src/Router.tsx")
LEGACY_LAYOUT = ("libs/shared/services/translate/src/lib/locals/en/en.json",
                 "libs/shared/services/translate/src/lib/locals/de/de.json",
                 "apps/platform-app/src/Router.tsx")


def _repo(root, config=GENERIC_CONFIG, layout=GENERIC_LAYOUT):
    en, de, router = layout
    if config is not None:
        _write(root, ".maggy/review.yaml", config)
    _write(root, en, json.dumps(LOCALE))
    _write(root, de, json.dumps(LOCALE))
    _write(root, router, "<New/>\n<Route element={<Dashboard/>}/>\n{fooEnabled && <Gated/>}")
    _write(root, "src/Widget.tsx", "t('app.title'); t('app.items')")
    for comp in ("Dashboard", "Gated", "New"):
        _write(root, f"src/{comp}.tsx", "x")
    return root


def _blocking(file, title, detail="details"):
    return Finding(file=file, severity=Severity.blocking, title=title, detail=detail)


I18N = "Missing translation key"
FLAG = "Not feature-flagged"


def _git(root, *args):
    base = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*base, *args], check=True, capture_output=True)


def publish_base(root, *paths):
    """Commit ``paths`` (default: only the review config) as origin/main."""
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-f", *(paths or [CONFIG_PATH]))
    _git(root, "commit", "-qm", "base", "--allow-empty")
    _git(root, "update-ref", "refs/remotes/origin/main", "HEAD")


def _run(root, findings, base_ref="main"):
    if not (root / ".git").exists() and (root / CONFIG_PATH).exists():
        publish_base(root)
    return deterministic_fp_filter(findings, str(root), lambda _m: None, base_ref)


class TestNoConfig:
    def test_findings_pass_through_unchanged(self, tmp_path):
        _repo(tmp_path, config=None)
        findings = [_blocking("src/Widget.tsx", I18N), _blocking("src/Widget.tsx", FLAG)]
        kept, dropped = _run(tmp_path, findings)
        assert dropped == 0 and kept == findings

    def test_legacy_layout_without_config_is_not_special(self, tmp_path):
        _repo(tmp_path, config=None, layout=LEGACY_LAYOUT)
        _write(tmp_path, "src/Widget.tsx", "t('zenny.a')")
        findings = [_blocking("src/Widget.tsx", I18N), _blocking("src/Widget.tsx", FLAG)]
        kept, dropped = _run(tmp_path, findings)
        assert dropped == 0 and kept == findings

    def test_no_local_path(self):
        findings = [_blocking("a.tsx", I18N)]
        assert deterministic_fp_filter(findings, None, lambda _m: None) == (findings, 0)


class TestConfigLoading:
    def test_missing_file_returns_none(self, tmp_path):
        publish_base(tmp_path, ".")
        assert load_review_config(tmp_path, "main") is None

    def test_parses_keys(self, tmp_path):
        _write(tmp_path, ".maggy/review.yaml", GENERIC_CONFIG)
        publish_base(tmp_path)
        cfg = load_review_config(tmp_path, "main")
        assert cfg == RepoReviewConfig(translation_locales=["locales/en.json", "locales/de.json"],
                                       translation_key_prefix="app.", router_files=["src/Router.tsx"])

    @pytest.mark.parametrize("text", ["::not yaml: [", "- a list\n", "translation_locales: 5\n"])
    def test_invalid_config_is_ignored(self, tmp_path, text):
        _write(tmp_path, ".maggy/review.yaml", text)
        publish_base(tmp_path)
        assert load_review_config(tmp_path, "main") is None


class TestI18nWithConfig:
    def test_drops_when_all_keys_resolve(self, tmp_path):
        _repo(tmp_path)
        kept, dropped = _run(tmp_path, [_blocking("src/Widget.tsx", I18N)])
        assert (kept, dropped) == ([], 1)

    def test_keeps_when_key_missing_in_a_locale(self, tmp_path):
        _repo(tmp_path)
        _write(tmp_path, "locales/de.json", json.dumps({"app": {"title": "T"}}))
        finding = _blocking("src/Widget.tsx", I18N)
        assert _run(tmp_path, [finding]) == ([finding], 0)

    def test_keeps_hardcoded_string_claims(self, tmp_path):
        _repo(tmp_path)
        finding = _blocking("src/Widget.tsx", I18N, "hardcoded text")
        assert _run(tmp_path, [finding]) == ([finding], 0)

    def test_keys_outside_prefix_are_ignored(self, tmp_path):
        _repo(tmp_path)
        _write(tmp_path, "src/Widget.tsx", "t('other.key')")
        finding = _blocking("src/Widget.tsx", I18N)
        assert _run(tmp_path, [finding]) == ([finding], 0)

    def test_nits_are_never_dropped(self, tmp_path):
        _repo(tmp_path)
        nit = Finding(file="src/Widget.tsx", severity=Severity.nit, title=I18N, detail="d")
        assert _run(tmp_path, [nit]) == ([nit], 0)


class TestFlagWithConfig:
    def test_unrouted_sub_component_dropped(self, tmp_path):
        _repo(tmp_path)
        assert _run(tmp_path, [_blocking("src/Widget.tsx", FLAG)]) == ([], 1)

    def test_gated_route_dropped(self, tmp_path):
        _repo(tmp_path)
        assert _run(tmp_path, [_blocking("src/Gated.tsx", FLAG)]) == ([], 1)

    def test_new_ungated_route_kept(self, tmp_path):
        _repo(tmp_path)
        finding = _blocking("src/New.tsx", FLAG)
        assert _run(tmp_path, [finding]) == ([finding], 0)

    def test_route_on_base_branch_dropped(self, tmp_path):
        _repo(tmp_path)
        publish_base(tmp_path, ".")
        assert _run(tmp_path, [_blocking("src/New.tsx", FLAG)], base_ref="main") == ([], 1)


class TestLegacyEquivalentConfig:
    def test_old_hardcoded_behaviour_preserved(self, tmp_path):
        _repo(tmp_path, config=LEGACY_CONFIG, layout=LEGACY_LAYOUT)
        locale = json.dumps({"zenny": {"a": "A", "b_other": "B"}})
        _write(tmp_path, LEGACY_LAYOUT[0], locale)
        _write(tmp_path, LEGACY_LAYOUT[1], locale)
        _write(tmp_path, "src/Widget.tsx", "t('zenny.a'); t('zenny.b'); t('common.x')")
        new = _blocking("src/New.tsx", FLAG)
        findings = [_blocking("src/Widget.tsx", I18N), _blocking("src/Widget.tsx", FLAG), new]
        assert _run(tmp_path, findings) == ([new], 2)
