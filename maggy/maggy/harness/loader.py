"""Resolve the harness profile from its layers.

Precedence (low to high): shipped defaults < repo (unlocked keys) <
personal (~/.maggy/harness.yaml) < repo-locked (keys listed in `locked:`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from maggy.harness.errors import HarnessConfigError, schema_problems
from maggy.harness.layering import deep_merge, key_paths, provenance_of, split_locked
from maggy.harness.schema import HarnessProfile, shipped_defaults
from maggy.harness.secrets import find_secret_keys

REPO_PROFILE = Path(".maggy") / "harness.yaml"


@dataclass(frozen=True)
class ResolvedProfile:
    profile: HarnessProfile
    provenance: dict[str, str]


def default_personal_path() -> Path:
    return Path.home() / ".maggy" / "harness.yaml"


def resolve_profile(repo_root: Path | None = None,
                    personal_path: Path | None = None) -> ResolvedProfile:
    """Merge all layers; return the profile and each key's source."""
    personal = read_layer(personal_path or default_personal_path(), personal=True)
    repo = read_layer(repo_root / REPO_PROFILE) if repo_root else {}
    locked = list(repo.get("locked") or [])
    repo_free, repo_held = split_locked(repo, locked)
    personal_free, _ = split_locked(personal, locked)
    return _combine([("default", shipped_defaults()), ("repo", repo_free),
                     ("personal", personal_free), ("repo-locked", repo_held)])


def read_layer(path: Path, personal: bool = False) -> dict:
    """Load and validate one profile file; a missing or empty file is {}."""
    raw = _load_yaml(path)
    problems = [f"{key}: secret-looking key; keep credentials in the environment"
                for key in find_secret_keys(raw)]
    if personal and "locked" in raw:
        problems.append("locked: only allowed in the repo profile")
    problems += [] if personal else [f"{key}: only allowed in the personal profile"
                                     for key in _personal_only(raw)]
    if problems:
        raise HarnessConfigError(path, problems)
    try:
        HarnessProfile.model_validate(raw)
    except ValidationError as exc:
        raise HarnessConfigError(path, schema_problems(exc, raw)) from exc
    return raw


PERSONAL_ONLY = (("worker", "allow_host_execution"), ("evidence", "external_review"))


def _personal_only(raw: dict) -> list[str]:
    """A repo must not grant itself host execution (RFC §2.6.7) or send evidence to an
    external reviewer (§2.6.9)."""
    return [f"{section}.{key}" for section, key in PERSONAL_ONLY
            if isinstance(raw.get(section), dict) and key in raw[section]]


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 1}, column {mark.column + 1}: " if mark else ""
        raise HarnessConfigError(path, [f"<root>: invalid YAML at {where}{exc}"]) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise HarnessConfigError(path, ["<root>: top level must be a mapping of keys"])
    return data


def _combine(layers: list[tuple[str, dict]]) -> ResolvedProfile:
    merged: dict = {}
    provenance: dict[str, str] = {}
    for source, data in layers:
        merged = deep_merge(merged, data)
        provenance.update(provenance_of(data, source))
    try:
        profile = HarnessProfile.model_validate(merged)
    except ValidationError as exc:
        raise HarnessConfigError("<merged profile>", schema_problems(exc, merged)) from exc
    present = key_paths(profile.model_dump())
    return ResolvedProfile(profile, {k: v for k, v in provenance.items() if k in present})
