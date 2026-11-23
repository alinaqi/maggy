"""Name rules for worker env and auth-file declarations (RFC §2.6.1)."""

from __future__ import annotations

import re

# Never handed to a worker or a check, even when an adapter declares them as a provider key:
# AWG and forge credentials would let an agent write trusted evidence or push (§2.6.1, §2.6.5).
FORBIDDEN_PREFIXES = ("AWG_", "GITHUB_", "GH_", "GITLAB_", "AWS_", "SSH_", "MAGGY_")
SECRET_WORDS = ("TOKEN", "SECRET", "KEY", "PASSWORD", "PASSWD", "CREDENTIAL", "AUTH")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_forbidden(name: str) -> bool:
    return name.upper().startswith(FORBIDDEN_PREFIXES)


def looks_secret(name: str) -> bool:
    upper = name.upper()
    return is_forbidden(upper) or any(word in upper for word in SECRET_WORDS)


def provider_key_problem(name: str) -> str | None:
    if not ENV_NAME.match(name):
        return f"{name!r} is not an environment variable name"
    if is_forbidden(name):
        return f"{name} is a forbidden credential ({', '.join(FORBIDDEN_PREFIXES)}*)"
    return None


def auth_file_problem(path: str) -> str | None:
    """Auth files are read in place under HOME or an absolute path, never workspace-relative."""
    if not (path.startswith("~/") or path.startswith("/")):
        return f"{path!r} must start with '~/' or '/' (auth files are never workspace files)"
    if ".." in path.split("/"):
        return f"{path!r} must not contain '..'"
    return None
