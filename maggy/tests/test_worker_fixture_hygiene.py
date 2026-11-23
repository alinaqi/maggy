"""Fixture hygiene: coverage per CLI, provenance, flags, and scrubbing."""

from __future__ import annotations

import os
import pwd
import re

import pytest

from worker_fixture_helpers import FIXTURES, load_meta

CLIS = ["claude", "codex", "opencode", "pi", "text"]
FILES = sorted(p for p in FIXTURES.rglob("*") if p.is_file())
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
TOKEN = re.compile(r"(sk-[\w-]{10,}|gh[pousr]_\w{20,}|github_pat_\w{20,}|xox[abprs]-[\w-]{10,}"
                   r"|AKIA[0-9A-Z]{16}|eyJ[\w-]{10,}\.|Bearer\s+\S{10,}|\b[0-9a-f]{32,}\b"
                   r"|\b[A-Za-z0-9+/=_-]{48,}\b)")


@pytest.mark.parametrize("cli", CLIS)
def test_each_cli_has_success_error_and_quota_cases(cli):
    meta = load_meta(cli)
    assert {"success", "error", "quota"} <= set(meta["cases"])
    for entry in meta["cases"].values():
        assert (FIXTURES / cli / entry["file"]).is_file()
        assert {"command", "date", "synthetic"} <= set(entry)


def test_every_fixture_file_is_described_by_meta():
    described = {FIXTURES / cli / "meta.yaml" for cli in CLIS}
    for cli in CLIS:
        meta = load_meta(cli)
        described |= {FIXTURES / cli / e["file"] for e in meta["cases"].values()}
        described |= {FIXTURES / cli / meta["help"]} if "help" in meta else set()
    assert set(FILES) == described


@pytest.mark.parametrize("cli", ["claude", "codex"])
def test_claude_and_codex_success_are_real_recordings(cli):
    assert load_meta(cli)["cases"]["success"]["synthetic"] is False


@pytest.mark.parametrize("cli", ["claude", "codex", "opencode", "pi"])
def test_recorded_flags_appear_in_versioned_help_excerpt(cli):
    meta = load_meta(cli)
    help_text = (FIXTURES / cli / meta["help"]).read_text()
    assert meta["version"] in help_text.splitlines()[0]
    flags = {a for e in meta["cases"].values() for a in e["command"] if a.startswith("-")}
    for flag in flags:
        assert re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", help_text), flag


@pytest.mark.parametrize("path", FILES, ids=[str(p.relative_to(FIXTURES)) for p in FILES])
def test_fixture_is_scrubbed(path):
    text = path.read_text()
    real_home = pwd.getpwuid(os.getuid()).pw_dir
    assert real_home not in text and "/Users/" not in text and "/home/" not in text
    assert not EMAIL.search(text)
    assert not TOKEN.search(text), TOKEN.search(text)
    assert set(UUID.findall(text)) <= {ZERO_UUID}
