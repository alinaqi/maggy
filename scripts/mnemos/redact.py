"""Secret redaction for Claude transcript ingestion.

Runs on every text field before it lands in SQLite. Patterns are applied
in priority order so more specific prefixes (Anthropic, Stripe) are tagged
before generic fallbacks (OpenAI sk-, dotenv-style key=value).
"""

from __future__ import annotations

import re

# Order matters: earlier patterns consume bytes so later ones don't double-tag.
# Each tuple is (kind, compiled_regex).
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # PEM blocks (multi-line)
    ('pem', re.compile(
        r'-----BEGIN [A-Z ]+-----[\s\S]+?-----END [A-Z ]+-----'
    )),
    # Slack webhook URLs
    ('slack_webhook', re.compile(
        r'https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+'
    )),
    # JWTs (three base64url chunks separated by dots; require at least 20
    # chars after the header to avoid matching short `eyJ...` fragments).
    ('jwt', re.compile(
        r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'
    )),
    # Anthropic API keys (must check before generic sk- to keep kind correct)
    ('anthropic_key', re.compile(
        r'sk-ant-[A-Za-z0-9_-]{40,}'
    )),
    # Stripe secret/publishable keys (underscore-separated; distinct from OpenAI sk-)
    ('stripe_key', re.compile(
        r'[sp]k_(?:live|test)_[A-Za-z0-9]{20,}'
    )),
    # OpenAI API keys (dash-separated; won't match `sk_live_` above)
    ('openai_key', re.compile(
        r'sk-[A-Za-z0-9_-]{20,}'
    )),
    # GitHub personal/app/oauth/refresh/user tokens
    ('github_token', re.compile(
        r'gh[pousr]_[A-Za-z0-9]{30,}'
    )),
    # AWS access key IDs
    ('aws_access_key', re.compile(
        r'AKIA[0-9A-Z]{16}'
    )),
    # Dotenv / config-style "password=..." "api_key: ..." etc.
    # Requires a recognised key name, a separator, then a non-whitespace value.
    # Value class excludes `[` to avoid re-consuming `[REDACTED:...]` tokens
    # left by earlier patterns.
    ('credential', re.compile(
        r'(?i)(?:password|api[_-]?key|secret|access[_-]?token|bearer|'
        r'aws_secret_access_key)["\':\s=]+[^\s"\'<>,;\[\]]{6,}'
    )),
]


def redact(text: str) -> tuple[str, int]:
    """Replace matches with [REDACTED:<kind>]. Returns (text, match_count).

    Safe on None/empty input -- returns ('', 0). Order-sensitive: patterns
    are applied top-down so specific prefixes win over generic fallbacks.
    """
    if not text:
        return '', 0

    total = 0
    for kind, pattern in _PATTERNS:
        token = f'[REDACTED:{kind}]'
        text, n = pattern.subn(token, text)
        total += n
    return text, total
