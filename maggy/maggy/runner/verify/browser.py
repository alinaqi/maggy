"""Render a Maggy visual check with Python Playwright (factory doc §5 "Render the actual
candidate"): a fresh context per viewport with fixed locale, time zone, scale and reduced
motion; only file:// requests inside the checkout are served (checks get no network and
no other local file, RFC §2.6.1); the
screenshot is taken after the layout assertions with animations off and the caret hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from maggy.runner.stages.visual_models import Action, Viewport, VisualSpec
from maggy.runner.verify.layout import problems

TIMEOUT_MS = 15_000


class BrowserUnavailable(RuntimeError):
    """Playwright or its browser cannot run here: the visual check stays PENDING."""


@dataclass
class Capture:
    viewport: str
    image: Path | None
    problems: list[str] = field(default_factory=list)


def render(spec: VisualSpec, checkout: Path, out_dir: Path) -> list[Capture]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserUnavailable("playwright is not installed (maggy[visual])") from exc
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:  # no browser downloaded or unsupported platform
            raise BrowserUnavailable(f"chromium cannot launch: {exc}"[:300]) from exc
        try:
            return [_capture(browser, spec, (checkout, out_dir, vp)) for vp in spec.viewports]
        finally:
            browser.close()


def _capture(browser: object, spec: VisualSpec, where: tuple[Path, Path, Viewport]) -> Capture:
    checkout, out_dir, viewport = where
    context = browser.new_context(
        viewport={"width": viewport.width, "height": viewport.height}, device_scale_factor=1,
        locale="en-US", timezone_id="UTC", reduced_motion="reduce", color_scheme="light")
    root = checkout.resolve().as_uri() + "/"
    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(root)
                  else route.abort())
    page = context.new_page()
    page.set_default_timeout(TIMEOUT_MS)
    try:
        return _drive(page, spec, (checkout, out_dir, viewport))
    except Exception as exc:  # a missing selector or a crashed page fails the check
        return Capture(viewport.name, None, [f"render: {str(exc).splitlines()[0]}"[:300]])
    finally:
        context.close()


def _drive(page: object, spec: VisualSpec, where: tuple[Path, Path, Viewport]) -> Capture:
    checkout, out_dir, viewport = where
    target = (checkout / spec.route).resolve()
    if not target.is_relative_to(checkout.resolve()):
        raise ValueError(f"route {spec.route} resolves outside the checkout")
    page.goto(target.as_uri())
    for action in spec.actions:
        _act(page, action)
    page.evaluate("document.fonts.ready.then(() => undefined)")
    found = problems(page, viewport, spec.assertions)
    page.mouse.move(0, 0)
    image = out_dir / f"{viewport.name}-actual.png"
    page.screenshot(path=str(image), animations="disabled", caret="hide")
    return Capture(viewport.name, image, found)


ACTIONS = {"fill": lambda locator, value: locator.fill(value),
           "click": lambda locator, _: locator.click(),
           "press": lambda locator, value: locator.press(value),
           "wait_for": lambda locator, _: locator.wait_for(state="visible")}


def _act(page: object, action: Action) -> None:
    ACTIONS[action.do](page.locator(action.selector).first, action.value)

