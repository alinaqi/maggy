"""Tests for the build-in-public voice rules."""

from __future__ import annotations

import importlib.util
import pathlib
import random
import sys
import types

_BIP = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "build-in-public"


def _load(modname, filename):
    pkg = "maggy.plugins.build_in_public"
    if pkg not in sys.modules:
        m = types.ModuleType(pkg)
        m.__path__ = [str(_BIP)]
        sys.modules[pkg] = m
    spec = importlib.util.spec_from_file_location(f"{pkg}.{modname}", _BIP / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"{pkg}.{modname}"] = mod
    spec.loader.exec_module(mod)
    return mod


voice = _load("voice", "voice.py")


# ── em dash ────────────────────────────────────────────────────────────

def test_removes_em_dash():
    out = voice.remove_em_dashes("we shipped it—then tested")
    assert "—" not in out and "shipped it, then tested" in out


def test_removes_en_dash_and_collapses_spaces():
    assert "–" not in voice.remove_em_dashes("a – b")


# ── markdown stripping ─────────────────────────────────────────────────

def test_strip_markdown_bold_italic_code():
    out = voice.strip_markdown("**bold** and *it* and `code`")
    assert out == "bold and it and code"


def test_strip_markdown_headers_and_links():
    out = voice.strip_markdown("# Title\nsee [docs](http://x.io)")
    assert "#" not in out
    assert "docs (http://x.io)" in out


def test_strip_markdown_bullets_plain():
    out = voice.strip_markdown("* one\n* two")
    assert "* one" not in out and "- one" in out


# ── typos (deterministic via seed) ─────────────────────────────────────

def test_typos_change_text_but_stay_close():
    rng = random.Random(42)
    src = "Maggy now routes requests across multiple models automatically today"
    out = voice.inject_typos(src, rate=1.0, rng=rng)
    assert out != src
    assert len(out.split()) == len(src.split())  # no words lost


def test_typos_zero_rate_is_noop():
    assert voice.inject_typos("hello world", rate=0.0) == "hello world"


def test_typos_skip_short_words():
    # rate 1.0 but short words unchanged
    assert voice.inject_typos("a to be", rate=1.0, rng=random.Random(1)) == "a to be"


# ── pipeline + config ──────────────────────────────────────────────────

def test_apply_voice_pipeline():
    rng = random.Random(7)
    out = voice.apply_voice("**Shipped**—fast", rng=rng)
    assert "**" not in out and "—" not in out


def test_apply_voice_respects_disabled_rules():
    out = voice.apply_voice("**keep**—dash",
                            {"strip_markdown": False, "no_em_dash": False,
                             "typos": {"enabled": False}})
    assert out == "**keep**—dash"


def test_resolve_voice_channel_override():
    cfg = {
        "voice": {"no_em_dash": True, "strip_markdown": True},
        "channels": {"reddit": {"voice": {"typos": {"enabled": False}}}},
    }
    v = voice.resolve_voice(cfg, "reddit")
    assert v["no_em_dash"] is True
    assert v["typos"] == {"enabled": False}
