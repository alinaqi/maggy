"""Deterministic FP filter: "missing translation key" claims checked against locale files."""

from __future__ import annotations

import json

from fp_filter_helpers import I18N, blocking, make_repo, run_filter, write
from maggy.review.models import Finding, Severity


class TestI18nWithConfig:
    def test_drops_when_all_keys_resolve(self, tmp_path):
        make_repo(tmp_path)
        kept, dropped = run_filter(tmp_path, [blocking("src/Widget.tsx", I18N)])
        assert (kept, dropped) == ([], 1)

    def test_keeps_when_key_missing_in_a_locale(self, tmp_path):
        make_repo(tmp_path)
        write(tmp_path, "locales/de.json", json.dumps({"app": {"title": "T"}}))
        finding = blocking("src/Widget.tsx", I18N)
        assert run_filter(tmp_path, [finding]) == ([finding], 0)

    def test_keeps_hardcoded_string_claims(self, tmp_path):
        make_repo(tmp_path)
        finding = blocking("src/Widget.tsx", I18N, "hardcoded text")
        assert run_filter(tmp_path, [finding]) == ([finding], 0)

    def test_keys_outside_prefix_are_ignored(self, tmp_path):
        make_repo(tmp_path)
        write(tmp_path, "src/Widget.tsx", "t('other.key')")
        finding = blocking("src/Widget.tsx", I18N)
        assert run_filter(tmp_path, [finding]) == ([finding], 0)

    def test_nits_are_never_dropped(self, tmp_path):
        make_repo(tmp_path)
        nit = Finding(file="src/Widget.tsx", severity=Severity.nit, title=I18N, detail="d")
        assert run_filter(tmp_path, [nit]) == ([nit], 0)
