"""Typer commands whose options live in a dataclass.

`options_command(Opts)(fn)` turns `fn(ctx, opts: Opts)` into a Typer command
whose CLI options are Opts' fields (each default is a typer.Option). Typer
reads the generated __signature__, so commands stay small and readable.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import fields
from functools import update_wrapper
from typing import Any, get_type_hints

import typer

_KW = inspect.Parameter.KEYWORD_ONLY


def _signature(options: type) -> inspect.Signature:
    hints = get_type_hints(options)
    params = [inspect.Parameter("ctx", _KW, annotation=typer.Context)]
    params += [inspect.Parameter(f.name, _KW, default=f.default, annotation=hints[f.name])
               for f in fields(options)]
    return inspect.Signature(params)


def options_command(options: type) -> Callable[[Callable], Callable]:
    def wrap(fn: Callable[[typer.Context, Any], None]) -> Callable:
        def command(ctx: typer.Context, **values: Any) -> None:
            fn(ctx, options(**values))

        update_wrapper(command, fn)
        del command.__wrapped__
        command.__signature__ = _signature(options)
        command.__annotations__ = {p.name: p.annotation for p in command.__signature__.parameters.values()}
        return command
    return wrap
