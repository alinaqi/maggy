"""Shared fixtures for the deterministic FP-filter tests (per-repo .maggy/review.yaml)."""

from __future__ import annotations

import json
import subprocess

from maggy.review.models import Finding, Severity
from maggy.review.fp_filter import FPFilterRun
from maggy.review.pipeline import deterministic_fp_filter
from maggy.review.repo_config import CONFIG_PATH

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
GENERIC_LAYOUT = ("locales/en.json", "locales/de.json", "src/Router.tsx")
LEGACY_LAYOUT = ("libs/shared/services/translate/src/lib/locals/en/en.json",
                 "libs/shared/services/translate/src/lib/locals/de/de.json",
                 "apps/platform-app/src/Router.tsx")
I18N = "Missing translation key"
FLAG = "Not feature-flagged"


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def make_repo(root, config=GENERIC_CONFIG, layout=GENERIC_LAYOUT):
    en, de, router = layout
    if config is not None:
        write(root, ".maggy/review.yaml", config)
    write(root, en, json.dumps(LOCALE))
    write(root, de, json.dumps(LOCALE))
    write(root, router, "<New/>\n<Route element={<Dashboard/>}/>\n{fooEnabled && <Gated/>}")
    write(root, "src/Widget.tsx", "t('app.title'); t('app.items')")
    for comp in ("Dashboard", "Gated", "New"):
        write(root, f"src/{comp}.tsx", "x")
    return root


def blocking(file, title, detail="details"):
    return Finding(file=file, severity=Severity.blocking, title=title, detail=detail)


def _git(root, *args):
    base = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*base, *args], check=True, capture_output=True)


def publish_base(root, *paths):
    """Commit ``paths`` (default: only the review config) as origin/main."""
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-f", *(paths or [CONFIG_PATH]))
    _git(root, "commit", "-qm", "base", "--allow-empty")
    _git(root, "update-ref", "refs/remotes/origin/main", "HEAD")


def run_filter(root, findings, on_log=None):
    """Run the filter against origin/main (the published base)."""
    if not (root / ".git").exists() and (root / CONFIG_PATH).exists():
        publish_base(root)
    return deterministic_fp_filter(findings, FPFilterRun(str(root), on_log or (lambda _m: None), "main"))
