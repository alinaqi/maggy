"""Safe argv templating: placeholders only as whole argv elements.

Values are inserted verbatim and never re-scanned, so prompt text (braces,
quotes, `$(...)`, `--flags`) is always exactly one literal argv element.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

WHOLE = frozenset({"{prompt}", "{model}", "{workspace}"})
SPLATS = frozenset({"{permission_flags}", "{model_flags}", "{awg_off_flags}",
                    "{budget_flags}"})
_PLACEHOLDER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


@dataclass(frozen=True)
class ArgvValues:
    prompt: str
    workspace: str
    permission: str
    model: str | None = None
    budget_usd: float | None = None


def placeholder_problem(element: str, allowed: frozenset[str]) -> str | None:
    """Why `element` is not a valid template element, or None if it is."""
    found = _PLACEHOLDER.findall(element)
    if not found:
        return None
    if element != found[0]:
        return f"embedded placeholder {found[0]} in {element!r}; use a whole argv element"
    if element not in allowed:
        return f"unknown or disallowed placeholder {element}"
    return None


def render_argv(adapter, values: ArgvValues) -> list[str]:
    """Expand the adapter's argv template for one run."""
    argv: list[str] = []
    for element in adapter.argv:
        argv.extend(_expand(adapter, element, values))
    return argv


def render_cwd(adapter, workspace: str) -> str:
    return workspace if adapter.cwd == "{workspace}" else adapter.cwd


def _expand(adapter, element: str, values: ArgvValues) -> list[str]:
    if element in SPLATS:
        return _splat(adapter, element, values)
    if element == "{model}":
        return [_require_model(values)]
    whole = {"{prompt}": values.prompt, "{workspace}": values.workspace}
    return [whole.get(element, element)]


def _splat(adapter, element: str, values: ArgvValues) -> list[str]:
    if element == "{awg_off_flags}":
        return list(adapter.disable_awg.flags)
    if element == "{model_flags}":
        return _fill(adapter.model_flags, "{model}", values.model)
    if element == "{budget_flags}":
        budget = None if values.budget_usd is None else f"{values.budget_usd:.4f}"
        return _fill(adapter.budget_flags, "{budget_usd}", budget)
    if values.permission not in adapter.permissions:
        raise ValueError(f"adapter {adapter.name} has no permission profile {values.permission!r}")
    return list(adapter.permissions[values.permission])


def _fill(flags: list[str], placeholder: str, value: str | None) -> list[str]:
    """`flags` with `placeholder` replaced by `value`; no value drops the flags."""
    if value is None:
        return []
    return [value if flag == placeholder else flag for flag in flags]


def _require_model(values: ArgvValues) -> str:
    if values.model is None:
        raise ValueError("argv uses {model} but no model was given")
    return values.model
