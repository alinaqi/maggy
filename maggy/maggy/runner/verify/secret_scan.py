"""Secret scan before an artifact is referenced in a PR (RFC §2.6.9).

Three detectors: known token formats (GitHub, OpenAI/Anthropic-style `sk-`, AWS, Slack,
private keys, JWTs), high-entropy tokens of mixed case and digits, and the runner's own
secret env values (names that look secret). Binary artifacts (screenshots) are scanned for
the formats and env values only: compressed pixels look like entropy. Findings name the
detector, never the secret.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from maggy.worker.env_rules import looks_secret

PATTERNS = {
    "github token": re.compile(r"(gh[posur]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "api key (sk-)": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "aws access key": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
}
CANDIDATE = re.compile(r"[A-Za-z0-9_+/=-]{24,}")
MIN_ENTROPY = 4.0
MIN_SECRET_LEN = 8
MAX_BYTES = 20_000_000


def scan_file(path: Path, env: Mapping[str, str]) -> list[str]:
    """What looks secret in `path` (detector labels); unreadable or huge files are flagged."""
    try:
        data = path.read_bytes() if path.stat().st_size <= MAX_BYTES else None
    except OSError as exc:
        return [f"unreadable: {type(exc).__name__}"]
    if data is None:
        return ["too large to scan"]
    if b"\0" in data:
        return scan_text(data.decode("latin-1"), env, entropy=False)
    return scan_text(data.decode("utf-8", errors="replace"), env)


def scan_text(text: str, env: Mapping[str, str], entropy: bool = True) -> list[str]:
    """Detector labels for `text`; `entropy=False` for binary data (compressed pixels)."""
    found = [label for label, pattern in PATTERNS.items() if pattern.search(text)]
    found += [f"value of ${name}" for name, value in _secret_values(env) if value in text]
    if entropy and any(_random(token) for token in CANDIDATE.findall(text)):
        found.append("high-entropy token")
    return found


def referable(paths: list[Path], env: Mapping[str, str]) -> tuple[list[Path], dict[Path, list[str]]]:
    """(paths safe to reference in a PR, withheld paths with their findings)."""
    withheld = {path: found for path in paths if (found := scan_file(path, env))}
    return [path for path in paths if path not in withheld], withheld


def _secret_values(env: Mapping[str, str]) -> list[tuple[str, str]]:
    return [(name, value) for name, value in env.items()
            if looks_secret(name) and len(value) >= MIN_SECRET_LEN]


def _random(token: str) -> bool:
    """Mixed upper, lower and digits with high entropy: a key, not a word, path or hex SHA."""
    classes = (re.search(r"[A-Z]", token), re.search(r"[a-z]", token), re.search(r"\d", token))
    return all(classes) and _entropy(token) >= MIN_ENTROPY


def _entropy(token: str) -> float:
    counts = Counter(token)
    return -sum(n / len(token) * math.log2(n / len(token)) for n in counts.values())
