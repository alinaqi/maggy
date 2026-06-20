"""Model roster, cost model, and key/token resolution for the council reviewer.

Adapted from revir for Maggy: provider keys come from the Maggy process
environment (Maggy already loads its own config/.env into os.environ), the
GitHub token is resolved from a per-request override / Maggy config / env, and
``load_skill`` is delegated to the extensible language registry. The model
ROSTER and pricing are unchanged from revir.
"""
from __future__ import annotations

import os

# load_skill lives in the language registry now; re-exported for pipeline compat.
from .languages import load_skill  # noqa: F401


def load_env() -> None:
    """Normalize provider key aliases. Maggy already populated os.environ from
    its own config/.env, so there is no revir/.env to read here."""
    if os.environ.get("XAI_API_KEY") and not os.environ.get("GROK_API_KEY"):
        os.environ["GROK_API_KEY"] = os.environ["XAI_API_KEY"]


def resolve_token(override: str | None = None, config_token: str | None = None) -> str | None:
    """GitHub token resolution: per-request override > Maggy config > env.

    Returns None when no token is configured anywhere (callers raise a clear
    error rather than calling GitHub unauthenticated)."""
    for candidate in (override, config_token, os.environ.get("GITHUB_TOKEN")):
        if candidate and candidate.strip():
            return candidate.strip()
    return None


def _gpt():
    from pydantic_ai.models.openai import OpenAIResponsesModel  # gpt-5.5-pro is Responses-only
    return OpenAIResponsesModel(os.environ.get("OPENAI_REVIEW_MODEL", "gpt-5.5-pro-2026-04-23"))


# CS-legend roster: (codename, model-factory, label, required-env-key, tool_capable)
# tool_capable=False -> reviews tool-lessly (diff embedded in the prompt).
ROSTER = [
    ("Lovelace", lambda: "deepseek:deepseek-chat", "DeepSeek", "DEEPSEEK_API_KEY", False),
    ("Hopper", lambda: "google:gemini-3.1-pro-preview", "Gemini 3.1 Pro", "GEMINI_API_KEY", True),
    ("Turing", lambda: "grok:grok-3", "Grok 3", "GROK_API_KEY", True),
    ("Dijkstra", _gpt, "GPT-5.5-pro", "OPENAI_API_KEY", True),
    ("Knuth", lambda: "google:gemini-3.5-flash", "Gemini 3.5 Flash", "GEMINI_API_KEY", True),
]
CHAIR = "Knuth"  # planner + synthesizer (cheap, tool-capable)


def available():
    """Roster entries whose API key is present, as (name, factory, label, tool_capable)."""
    load_env()
    out = []
    for name, factory, label, need, tools in ROSTER:
        keys = [need] + (["GOOGLE_API_KEY"] if need == "GEMINI_API_KEY" else [])
        if any(os.environ.get(k) for k in keys):
            out.append((name, factory, label, tools))
    return out


# approximate public $ per 1M tokens (input, output) — cost estimation only
PRICING = {
    "gemini": (0.30, 2.50),
    "gemini-3.5": (0.50, 3.00),
    "gemini-3.1-pro": (1.25, 10.00),
    "deepseek": (0.28, 0.42),
    "grok": (3.00, 15.00),
    "gpt-5.5": (15.00, 120.00),
}
PRICING_KEY = {"Lovelace": "deepseek", "Hopper": "gemini-3.1-pro", "Turing": "grok",
               "Dijkstra": "gpt-5.5", "Knuth": "gemini-3.5"}


def cost_usd(model_key, input_tokens, output_tokens, cache_read_tokens=0):
    """Cost in USD. Cached input (implicit caching) billed at ~25% of input rate."""
    p = PRICING.get(model_key)
    if not p:
        return 0.0
    cached = min(cache_read_tokens or 0, input_tokens)
    fresh = input_tokens - cached
    return (fresh / 1e6 * p[0] + cached / 1e6 * p[0] * 0.25 + output_tokens / 1e6 * p[1])
