"""Typed AWG failures, mapped from the awg CLI's stable error codes (never carrying a secret)."""

from __future__ import annotations

import json
import re


class AwgError(RuntimeError):
    """Any awg failure; `code` is AWG's stable error code (or a local one)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class LeaseLost(AwgError):
    """The runner no longer holds the lease: stop, skip every side effect (§2.6.3)."""


class FenceStale(LeaseLost):
    """The presented attempt/fencing token is not the live lease."""


class Unauthorized(AwgError):
    """The credential is missing, invalid or lacks the scope."""


class NotFound(AwgError):
    """No such work item."""


class AwgUnavailable(AwgError):
    """awg could not be run or asked to retry later."""


CODES: dict[str, type[AwgError]] = {
    "stale_fencing_token": FenceStale, "stale_version": FenceStale,
    "lease_lost": LeaseLost, "lease_expired": LeaseLost, "no_lease": LeaseLost,
    "unauthorized": Unauthorized, "forbidden": Unauthorized, "not_found": NotFound,
    "unavailable": AwgUnavailable, "in_progress": AwgUnavailable,
    "rate_limited": AwgUnavailable, "not_initialized": AwgUnavailable,
}

_STDERR = re.compile(r"awg: ([a-z_]+): (.*)")


def error_for(code: str, message: str) -> AwgError:
    return CODES.get(code, AwgError)(code, message[:300])


def parse_failure(stdout: str, stderr: str) -> AwgError:
    """The typed error for a non-zero awg exit: JSON error body first, then `awg: code: msg`."""
    found = _json_error(stdout) or _json_error(stderr)
    if found:
        return error_for(str(found.get("code", "error")), str(found.get("message", "")))
    if "no lease held" in stderr:
        return error_for("no_lease", stderr.strip())
    match = _STDERR.search(stderr)
    if match:
        return error_for(match.group(1), match.group(2))
    return error_for("error", stderr.strip() or stdout.strip() or "awg failed")


def _json_error(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except ValueError:
        return None
    error = data.get("error", data) if isinstance(data, dict) else None
    return error if isinstance(error, dict) and "code" in error else None
