"""Voice rules — make Maggy's posts sound human and Reddit-safe.

A small, user-definable transform pipeline applied to text before it is
posted or replied. Configure under `config.voice` in plugin.yaml (or
per-channel `channels.<ch>.voice`). Every rule is opt-in via config so each
Maggy install keeps its own voice.

Rules:
  no_em_dash      — replace em/en dashes (Reddit/readers dislike them)
  strip_markdown  — flatten Markdown to plain text (Reddit fancy-editor
                    renders stray Markdown literally; keep it clean)
  typos           — inject occasional realistic typos so posts read human
"""

from __future__ import annotations

import random
import re

# Default voice if a channel/global config provides none.
DEFAULT_VOICE = {
    "no_em_dash": True,
    "strip_markdown": True,
    "typos": {"enabled": True, "rate": 0.03},
}


def remove_em_dashes(text: str, replacement: str = ", ") -> str:
    """Replace em/en/figure dashes; collapse the spacing they leave behind."""
    out = re.sub(r"\s*[—–‒]\s*", replacement, text)
    return re.sub(r"[ \t]{2,}", " ", out)


def strip_markdown(text: str) -> str:
    """Flatten Markdown to plain text Reddit won't mangle."""
    t = text
    t = re.sub(r"```.*?```", lambda m: m.group(0).strip("`"), t, flags=re.DOTALL)
    t = re.sub(r"`([^`]+)`", r"\1", t)                       # inline code
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)               # images
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", t)    # links -> text (url)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.MULTILINE)  # headers
    t = re.sub(r"^\s{0,3}>\s?", "", t, flags=re.MULTILINE)   # blockquotes
    t = re.sub(r"^\s{0,3}[-*_]{3,}\s*$", "", t, flags=re.MULTILINE)  # hrules
    t = re.sub(r"(\*\*|__)(.+?)\1", r"\2", t)                # bold
    t = re.sub(r"(\*|_)(.+?)\1", r"\2", t)                   # italic
    t = re.sub(r"^\s{0,3}[-*+]\s+", "- ", t, flags=re.MULTILINE)  # bullets -> plain
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _typo_word(word: str, rng: random.Random) -> str:
    """Apply one realistic typo to a word (len>=4, alphabetic core)."""
    if len(word) < 4 or not word.isalpha():
        return word
    op = rng.choice(("transpose", "drop", "double"))
    i = rng.randint(1, len(word) - 2)
    if op == "transpose":
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    if op == "drop":
        return word[:i] + word[i + 1:]
    return word[:i] + word[i] + word[i:]  # double


def inject_typos(text: str, rate: float = 0.03,
                 rng: random.Random | None = None) -> str:
    """Randomly typo ~`rate` of eligible words. Seed `rng` for determinism."""
    if rate <= 0:
        return text
    rng = rng or random.Random()
    tokens = re.split(r"(\s+)", text)
    out = []
    for tok in tokens:
        if tok.strip() and rng.random() < rate:
            out.append(_typo_word(tok, rng))
        else:
            out.append(tok)
    return "".join(out)


def apply_voice(text: str, rules: dict | None = None,
                rng: random.Random | None = None) -> str:
    """Run the configured voice pipeline over `text`."""
    if not text:
        return text
    rules = DEFAULT_VOICE if rules is None else rules
    out = text
    if rules.get("strip_markdown"):
        out = strip_markdown(out)
    if rules.get("no_em_dash"):
        out = remove_em_dashes(out, rules.get("em_dash_replacement", ", "))
    typos = rules.get("typos") or {}
    if typos.get("enabled"):
        out = inject_typos(out, typos.get("rate", 0.03), rng)
    return out


def resolve_voice(config: dict, channel: str) -> dict:
    """Merge global `config.voice` with a per-channel override."""
    base = dict(DEFAULT_VOICE)
    base.update(config.get("voice") or {})
    ch = (config.get("channels", {}).get(channel, {}) or {}).get("voice")
    if ch:
        base.update(ch)
    return base
