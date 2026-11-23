"""Personal harness: one profile, layered from defaults, repo and personal files."""

from maggy.harness.apply import ApplyReport, apply_changes
from maggy.harness.changes import FileChange, HarnessContext, ManagedFile
from maggy.harness.errors import HarnessConfigError
from maggy.harness.loader import ResolvedProfile, default_personal_path, resolve_profile
from maggy.harness.plan import plan_files
from maggy.harness.schema import HarnessProfile, shipped_defaults

__all__ = [
    "ApplyReport", "FileChange", "HarnessConfigError", "HarnessContext", "HarnessProfile",
    "ManagedFile", "ResolvedProfile", "apply_changes", "default_personal_path", "plan_files",
    "resolve_profile", "shipped_defaults",
]
