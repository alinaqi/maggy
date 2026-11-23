"""Deterministic false-positive filter (no LLM), configured per repo.

The two FP classes that dominate mega-PR reviews are MECHANICALLY checkable, so we
verify them in code instead of relying on a per-finding LLM (which is inconsistent):
  1. "missing translation key": read the repo's locale JSON files; if every key the
     file uses resolves in ALL locales, the claim is false.
  2. "not feature-flagged" on a sub-component: flag gating is an ENTRY-POINT concern;
     a component that isn't a routed entry point doesn't get its own flag.
Where locales and routers live comes from ``.maggy/review.yaml`` (see repo_config).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .repo_config import RepoReviewConfig, load_review_config

_RE_KEY = re.compile(r"""t\(\s*['"]([a-zA-Z0-9_.]+)['"]""")
_RE_I18N = re.compile(r"(i18n|translation|locale|missing.{0,15}key|de (locale|translation)|"
                      r"informal|not localized|missing 'de'|missing de)", re.IGNORECASE)
_RE_FLAG = re.compile(r"(feature.?flag|not gated|feature-flag|unconditional|not feature)", re.IGNORECASE)
_RE_GATE = re.compile(r"Enabled\s*&&|useFeatureFlag|can_use_\w+\s*&&|FF_\w+\s*&&")
_PLURALS = ("_one", "_other", "_plural", "_zero", "_many")


def _flat_keys(path):
    try:
        data = json.loads(Path(path).read_text())
    except Exception:  # noqa: BLE001
        return set()
    keys, stack = set(), [("", data)] if isinstance(data, dict) else []
    while stack:
        prefix, node = stack.pop()
        for k, v in node.items():
            stack.append((f"{prefix}{k}.", v)) if isinstance(v, dict) else keys.add(prefix + k)
    return keys


def _resolves(key, ks):
    return key in ks or any(key + s in ks for s in _PLURALS)


def _git_show(lp, ref, path):
    try:
        r = subprocess.run(["git", "-C", str(lp), "show", f"{ref}:{path}"],
                           check=False, capture_output=True, text=True, timeout=15)
        return r.stdout if r.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return ""


def _routed(comp, router_text):
    # a component is a routed entry point if its name appears as a word in the router
    return bool(comp) and re.search(rf"\b{re.escape(comp)}\b", router_text) is not None


def _gated(comp, router_text):
    # is the component's mount inside a feature-flag conditional? (e.g. {fooEnabled && <X/>})
    hits = re.finditer(rf"\b{re.escape(comp)}\b", router_text)
    return any(_RE_GATE.search(router_text[max(0, m.start() - 400):m.start()]) for m in hits)


def _context(lp, cfg: RepoReviewConfig, base_ref):
    """Locale key sets, the current router text and the base-branch router text."""
    locales = [_flat_keys(lp / p) for p in cfg.translation_locales]
    paths = [lp / p for p in cfg.router_files]
    router = "\n".join(p.read_text(errors="replace") for p in paths if p.exists())
    # the base branch's routers tell a NEW ungated route from a pre-existing one
    base = "\n".join(_git_show(lp, f"origin/{base_ref}", p) for p in cfg.router_files) if base_ref else ""
    return {"locales": locales, "router": router, "base": base, "prefix": cfg.translation_key_prefix}


def _i18n_reason(blob, fpath, ctx):
    locales = ctx["locales"]
    if not (locales and all(locales) and _RE_I18N.search(blob)) or "hardcod" in blob or not fpath.exists():
        return None
    used = {k for k in _RE_KEY.findall(fpath.read_text(errors="replace")) if k.startswith(ctx["prefix"])}
    if used and all(_resolves(k, ks) for k in used for ks in locales):
        return f"i18n FP dropped: {{}} ({len(used)} keys all resolve in every locale)"
    return None


def _flag_reason(blob, comp, ctx):
    router, base = ctx["router"], ctx["base"]
    if not (router and _RE_FLAG.search(blob)):
        return None
    if not _routed(comp, router):
        return f"flag FP dropped: {{}} ({comp} is a sub-component, not a route)"
    if base and _routed(comp, base):
        return f"flag FP dropped: {{}} ({comp} route pre-exists on base)"
    if _gated(comp, router):
        return f"flag FP dropped: {{}} ({comp} is already behind a feature flag)"
    return None


def _fp_reason(f, lp, ctx):
    if getattr(f.severity, "value", f.severity) != "blocking":
        return None
    blob = f"{f.title} {f.detail}".lower()
    return _i18n_reason(blob, lp / f.file, ctx) or _flag_reason(blob, Path(f.file).stem, ctx)


def deterministic_fp_filter(findings, local_path, on_log, base_ref=None):
    """Drop mechanically-disproved blocking findings; a no-op without repo config."""
    cfg = load_review_config(local_path) if local_path else None
    if cfg is None:
        return findings, 0
    lp = Path(local_path)
    ctx = _context(lp, cfg, base_ref)
    kept = []
    for f in findings:
        reason = _fp_reason(f, lp, ctx)
        if reason:
            on_log("[det-fp] " + reason.format(f.title[:55]))
        else:
            kept.append(f)
    return kept, len(findings) - len(kept)
