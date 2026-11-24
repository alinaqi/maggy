"""Browser layout assertions for a Maggy visual check (factory doc §5 "Check the layout").

Each returns None when it holds, else what broke (named by selector), so a FAIL says which
expectation of the criterion the candidate missed.
"""

from __future__ import annotations

from collections.abc import Callable

from maggy.runner.stages.visual_models import LayoutAssertion, Viewport

Box = dict[str, float]


def problems(page: object, viewport: Viewport, assertions: list[LayoutAssertion]) -> list[str]:
    return [found for check in assertions
            if (found := CHECKS[check.check](page, viewport, check)) is not None]


def _box(page: object, selector: str) -> Box | None:
    locator = page.locator(selector).first
    return locator.bounding_box() if locator.count() else None


def _visible(page: object, viewport: Viewport, check: LayoutAssertion) -> str | None:
    locator = page.locator(check.selector).first
    shown = locator.count() and locator.is_visible()
    return None if shown else f"visible: {check.selector} is not visible"


def _in_viewport(page: object, viewport: Viewport, check: LayoutAssertion) -> str | None:
    box = _box(page, check.selector)
    inside = box is not None and box["width"] > 0 and box["x"] >= 0 and box["y"] >= 0 and (
        box["x"] + box["width"] <= viewport.width and box["y"] + box["height"] <= viewport.height)
    return None if inside else f"in_viewport: {check.selector} is not fully in view at {viewport.name}"


def _below(page: object, viewport: Viewport, check: LayoutAssertion) -> str | None:
    box, other = _box(page, check.selector), _box(page, check.other)
    if box is None or other is None:
        return f"below: {check.selector} or {check.other} is missing"
    under = box["y"] >= other["y"] + other["height"]
    overlaps = box["x"] < other["x"] + other["width"] and box["x"] + box["width"] > other["x"]
    return None if under and overlaps else f"below: {check.selector} is not under {check.other}"


def _text(page: object, viewport: Viewport, check: LayoutAssertion) -> str | None:
    locator = page.locator(check.selector).first
    actual = locator.inner_text().strip() if locator.count() else None
    return None if actual == check.value else f"text: {check.selector} shows {actual!r}"


def _no_horizontal_scroll(page: object, viewport: Viewport, check: LayoutAssertion) -> str | None:
    width = page.evaluate("document.documentElement.scrollWidth")
    return None if width <= viewport.width else f"no_horizontal_scroll: page is {width}px wide"


CHECKS: dict[str, Callable[[object, Viewport, LayoutAssertion], str | None]] = {
    "visible": _visible, "in_viewport": _in_viewport, "below": _below, "text": _text,
    "no_horizontal_scroll": _no_horizontal_scroll,
}
