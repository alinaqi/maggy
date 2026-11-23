"""Structured stage output: one fenced json block validated against a Pydantic model.

Stage workers are told to end with exactly one ```json block. A reply that has none, more
than one, bad JSON or a shape the model rejects is answered once with the error; a second
bad reply raises StructuredError and the stage fails without touching the graph.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

Model = TypeVar("Model", bound=BaseModel)
FENCE = re.compile(r"```json[ \t]*\n(.*?)\n[ \t]*```", re.DOTALL | re.IGNORECASE)
RETRY = ("Your previous reply was rejected: {error}\nReply again, ending with exactly one "
         "fenced ```json block that matches the schema.")


class StructuredError(ValueError):
    """The agent's reply had no single valid json block."""


def parse_structured(text: str, model: type[Model]) -> Model:
    blocks = FENCE.findall(text)
    if len(blocks) != 1:
        raise StructuredError(f"expected exactly one fenced json block, found {len(blocks)}")
    try:
        return model.model_validate(json.loads(blocks[0]))
    except ValueError as exc:  # JSONDecodeError and ValidationError are both ValueErrors
        raise StructuredError(_describe(exc)) from exc


def _describe(exc: ValueError) -> str:
    if isinstance(exc, ValidationError):
        problems = [f"{'.'.join(map(str, e['loc'])) or '(root)'}: {e['msg']}"
                    for e in exc.errors()]
        return "schema: " + "; ".join(problems)[:800]
    return f"invalid JSON: {exc}"[:300]


def ask_structured(agent: Callable[[str], str], prompt: str, model: type[Model]) -> Model:
    """`agent(prompt)` parsed into `model`, retried once with the validation error."""
    try:
        return parse_structured(agent(prompt), model)
    except StructuredError as exc:
        retry = f"{RETRY.format(error=exc)}\n\n{prompt}"
        return parse_structured(agent(retry), model)
