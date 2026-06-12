"""Enable/disable srooter routing from the web UI by wrapping `srooterctl`.

`srooterctl` is the canonical tool — it writes ~/.claude/settings.json and
~/.srooter, wires the heartbeat/cortex hooks, and keeps an audit log. We shell
out to it (never reimplement the wiring) so the dashboard button and the CLI
stay in lockstep. One click = `srooterctl repair <key> [url]`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_FALLBACK = Path.home() / ".local" / "bin" / "srooterctl"
# srooter keys are url-safe tokens; reject shell metachars/spaces AND a leading
# hyphen, so the value can never be smuggled to srooterctl as a CLI flag
# (the CLI is positional bash — no `--` end-of-options sentinel to rely on).
_KEY_RE = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_.\-]{7,199}$")
_URL_RE = re.compile(r"^https?://[A-Za-z0-9.\-:/_]+$")
_TIMEOUT = 45


def find_srooterctl() -> str | None:
    """Locate the srooterctl executable, or None if it isn't installed."""
    found = shutil.which("srooterctl")
    if found:
        return found
    return str(_FALLBACK) if _FALLBACK.exists() else None


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run srooterctl with args (no shell), capturing combined output."""
    ctl = find_srooterctl()
    if not ctl:
        raise FileNotFoundError("srooterctl not installed")
    return subprocess.run(
        [ctl, *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        check=False,
    )


def _line_ok(lines: list[str], prefix: str) -> bool:
    """True when the doctor line starting with `prefix` reports OK."""
    return any(ln.strip().startswith(prefix) and "OK" in ln for ln in lines)


def _gateway(lines: list[str]) -> str:
    """Pull the gateway URL from the doctor header line."""
    for ln in lines:
        if ln.startswith("srooter doctor —"):
            return ln.split("—", 1)[1].strip()
    return ""


def _parse_doctor(text: str) -> dict:
    """Turn `srooterctl doctor` output into a status dict for the UI."""
    lines = text.splitlines()
    return {
        "installed": True,
        "enabled": _line_ok(lines, "claude routing"),
        "key_set": _line_ok(lines, "config"),
        "shell_routing": _line_ok(lines, "shell routing"),
        "gateway": _gateway(lines),
    }


def status() -> dict:
    """Current routing state. `installed=False` means srooterctl is absent."""
    if not find_srooterctl():
        return {
            "installed": False,
            "enabled": False,
            "hint": "srooter routing isn't installed yet. Get a key at srooter.ai.",
        }
    return _parse_doctor(_run(["doctor"]).stdout)


def enable(api_key: str = "", gateway_url: str = "") -> dict:
    """Wire srooter routing with one command. Returns the fresh status.

    Pass a key to configure (or rotate) it. With no key, reuse the one already
    saved by srooterctl — so a returning user enables with a single click.
    """
    key = api_key.strip()
    if not key:
        if not status().get("key_set"):
            raise ValueError("No saved key — paste your srooter API key.")
        _run(["repair"])
        return status()
    if not _KEY_RE.match(key):
        raise ValueError("Invalid API key — expected a srooter token, no spaces.")
    args = ["repair", key]
    url = gateway_url.strip()
    if url:
        if not _URL_RE.match(url):
            raise ValueError("Invalid gateway URL — must be http(s)://…")
        args.append(url)
    _run(args)
    return status()


def disable() -> dict:
    """Turn routing back to direct Anthropic. Returns the fresh status."""
    _run(["claude-env", "off"])
    _run(["disable"])
    return status()
