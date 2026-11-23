"""Per-repo review config: ``.maggy/review.yaml`` on the reviewed repo's BASE branch.

It tells the deterministic false-positive filter where a repo keeps its locale
files and router. The config is read from ``origin/<base>`` only, never from the
checkout: the checkout is the PR head, and a PR must not be able to switch the
filter on (or repoint it) to drop its own blocking findings. Paths must be
relative and stay inside the repo. Without a base ref, or with no or an invalid
config, the filter is a no-op.

Example::

    translation_locales: [locales/en.json, locales/de.json]
    translation_key_prefix: app.
    router_files: [src/Router.tsx]
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

CONFIG_PATH = ".maggy/review.yaml"
_DRIVE = re.compile(r"^[A-Za-z]:")


def _inside_repo(path: str) -> bool:
    parts = PurePosixPath(path.replace("\\", "/")).parts
    absolute = path.startswith(("/", "\\")) or bool(_DRIVE.match(path))
    return bool(parts) and not absolute and ".." not in parts


class RepoReviewConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    translation_locales: list[str] = []
    translation_key_prefix: str = ""
    router_files: list[str] = []

    @field_validator("translation_locales", "router_files")
    @classmethod
    def _relative_paths(cls, paths: list[str]) -> list[str]:
        bad = [p for p in paths if not _inside_repo(p)]
        if bad:
            raise ValueError(f"paths must be relative and inside the repo: {bad}")
        return paths


def parse_review_config(text: str) -> RepoReviewConfig | None:
    """Parse config YAML; None when it is not a valid config mapping."""
    try:
        data = yaml.safe_load(text)
        return RepoReviewConfig.model_validate(data) if isinstance(data, dict) else None
    except (yaml.YAMLError, ValidationError):
        return None


def load_review_config(repo_root: str | Path, base_ref: str | None) -> RepoReviewConfig | None:
    """Read the config from ``origin/<base_ref>``; None without a trusted base."""
    if not base_ref:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"origin/{base_ref}:{CONFIG_PATH}"],
            check=False, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_review_config(result.stdout) if result.returncode == 0 else None
