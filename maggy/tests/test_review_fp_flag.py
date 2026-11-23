"""Deterministic FP filter: "not feature-flagged" claims checked against router files."""

from __future__ import annotations

import json

from fp_filter_helpers import (FLAG, I18N, LEGACY_CONFIG, LEGACY_LAYOUT, blocking, make_repo,
                               publish_base, run_filter, write)


class TestFlagWithConfig:
    def test_unrouted_sub_component_dropped(self, tmp_path):
        make_repo(tmp_path)
        assert run_filter(tmp_path, [blocking("src/Widget.tsx", FLAG)]) == ([], 1)

    def test_gated_route_dropped(self, tmp_path):
        make_repo(tmp_path)
        assert run_filter(tmp_path, [blocking("src/Gated.tsx", FLAG)]) == ([], 1)

    def test_new_ungated_route_kept(self, tmp_path):
        make_repo(tmp_path)
        finding = blocking("src/New.tsx", FLAG)
        assert run_filter(tmp_path, [finding]) == ([finding], 0)

    def test_route_on_base_branch_dropped(self, tmp_path):
        make_repo(tmp_path)
        publish_base(tmp_path, ".")
        assert run_filter(tmp_path, [blocking("src/New.tsx", FLAG)]) == ([], 1)


class TestLegacyEquivalentConfig:
    def test_old_hardcoded_behaviour_preserved(self, tmp_path):
        make_repo(tmp_path, config=LEGACY_CONFIG, layout=LEGACY_LAYOUT)
        locale = json.dumps({"zenny": {"a": "A", "b_other": "B"}})
        write(tmp_path, LEGACY_LAYOUT[0], locale)
        write(tmp_path, LEGACY_LAYOUT[1], locale)
        write(tmp_path, "src/Widget.tsx", "t('zenny.a'); t('zenny.b'); t('common.x')")
        new = blocking("src/New.tsx", FLAG)
        findings = [blocking("src/Widget.tsx", I18N), blocking("src/Widget.tsx", FLAG), new]
        assert run_filter(tmp_path, findings) == ([new], 2)


class TestUntrustedTextInLog:
    def test_braces_in_file_name_do_not_crash(self, tmp_path):
        make_repo(tmp_path)
        logs = []
        kept, dropped = run_filter(tmp_path, [blocking("src/a{0}b.tsx", FLAG)], on_log=logs.append)
        assert (kept, dropped) == ([], 1)
        assert "a{0}b is a sub-component" in logs[0]

    def test_braces_in_title_are_logged_verbatim(self, tmp_path):
        make_repo(tmp_path)
        logs = []
        run_filter(tmp_path, [blocking("src/{x}.tsx", FLAG + " {}")], on_log=logs.append)
        assert logs == ["[det-fp] flag FP dropped: Not feature-flagged {} ({x} is a sub-component, not a route)"]
