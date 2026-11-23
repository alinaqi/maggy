"""Safe argv templating: placeholders only as whole argv elements.

Values are inserted verbatim and never re-scanned, so prompt text (braces,
quotes, `$(...)`, `--flags`) is always exactly one literal argv element.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

WHOLE = frozenset({"{prompt}", "{model}", "{workspace}"})
SPLATS = frozenset({"{permission_flags}", "{model_flags}", "{awg_off_flags}"})
_PLACEHOLDER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


@dataclass(frozen=True)
class ArgvValues:
    prompt: str
    workspace: str
    permission: str
    model: str | None = None


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
        if values.model is None:
            return []
        return [values.model if flag == "{model}" else flag for flag in adapter.model_flags]
    if values.permission not in adapter.permissions:
        raise ValueError(f"adapter {adapter.name} has no permission profile {values.permission!r}")
    return list(adapter.permissions[values.permission])


def _require_model(values: ArgvValues) -> str:
    if values.model is None:
        raise ValueError("argv uses {model} but no model was given")
    return values.model
