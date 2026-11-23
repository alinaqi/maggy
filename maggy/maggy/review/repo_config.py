"""Per-repo review config, read from ``.maggy/review.yaml`` in the reviewed repo.

It tells the deterministic false-positive filter where a repo keeps its locale
files and router. When there is no config (or it is invalid) the filter is a no-op.

Example::

    translation_locales: [locales/en.json, locales/de.json]
    translation_key_prefix: app.
    router_files: [src/Router.tsx]
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

CONFIG_PATH = ".maggy/review.yaml"


class RepoReviewConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    translation_locales: list[str] = []
    translation_key_prefix: str = ""
    router_files: list[str] = []


def load_review_config(repo_root: str | Path) -> RepoReviewConfig | None:
    """Parse the repo's review config; None when it is absent or invalid."""
    path = Path(repo_root) / CONFIG_PATH
    try:
        data = yaml.safe_load(path.read_text())
        return RepoReviewConfig.model_validate(data) if isinstance(data, dict) else None
    except (OSError, yaml.YAMLError, ValidationError):
        return None
