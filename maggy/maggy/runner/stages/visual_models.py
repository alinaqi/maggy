"""A Maggy-run visual check described by the test plan (factory doc §5 "Specify what to
look at"): a static route in the candidate checkout, the actions that reach the state, the
viewports and the layout assertions; the screenshot is compared against
`.maggy/baselines/<criterion>-<viewport>.png` in the candidate."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, field_validator

from maggy.runner.stages.models import Shape

NAME = r"^[A-Za-z0-9_-]{1,40}$"


class Viewport(Shape):
    name: str = Field(pattern=NAME)
    width: int = Field(gt=0, le=4096)
    height: int = Field(gt=0, le=4096)


class Action(Shape):
    do: Literal["fill", "click", "press", "wait_for"]
    selector: str = Field(min_length=1)
    value: str = ""


class LayoutAssertion(Shape):
    check: Literal["visible", "in_viewport", "below", "text", "no_horizontal_scroll"]
    selector: str = ""
    other: str = ""  # `below`: the element the selector must sit under
    value: str = ""  # `text`: the exact (stripped) text


class VisualSpec(Shape):
    route: str = Field(min_length=1)
    viewports: list[Viewport] = Field(min_length=1)
    actions: list[Action] = []
    assertions: list[LayoutAssertion] = []
    max_diff_pixels: int = Field(0, ge=0)

    @field_validator("route")
    @classmethod
    def _inside_checkout(cls, route: str) -> str:
        """Only a file of the candidate checkout: no scheme, absolute path or `..`."""
        path = PurePosixPath(route)
        if ":" in route or path.is_absolute() or ".." in path.parts:
            raise ValueError("route must be a relative file path inside the checkout")
        return route
