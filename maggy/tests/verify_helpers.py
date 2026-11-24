"""Verify-stage fixtures: the coupon checkout page (factory doc §1, §2, §5), its AC3 visual
check, a fake vision backend and the browser availability probe (skip elsewhere, run here)."""

from __future__ import annotations

import os
import pwd
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from maggy.runner.verify.vision import VisionRequest, VisionVerdict

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
body {{ margin: 0; font: 16px/1.4 sans-serif; background: #fff; color: #111; }}
main {{ padding: 16px; max-width: 480px; position: relative; }}
#coupon {{ display: block; width: 200px; height: 28px; }}
#apply {{ display: block; margin-top: 8px; height: 32px; }}
#coupon-error {{ color: #b00020; display: none; {error_css} }}
#order-total {{ margin-top: 16px; font-weight: bold; color: {total_color}; }}
</style></head><body><main>
<label for="coupon">Coupon code</label>
<input id="coupon" aria-label="Coupon code">
<p id="coupon-error" data-testid="coupon-error"></p>
<button id="apply">Apply</button>
<p id="order-total" data-testid="order-total">Total: $100</p>
</main><script>
document.getElementById('apply').addEventListener('click', () => {{
  const code = document.getElementById('coupon').value;
  const error = document.getElementById('coupon-error');
  if (code === 'EXPIRED') {{ error.textContent = 'This coupon has expired';
    error.style.display = 'block'; }}
}});
</script></body></html>
"""

GOOD_PAGE = PAGE.format(error_css="", total_color="#111")
RECOLOURED_PAGE = PAGE.format(error_css="", total_color="#0a0")
OVERLAP_PAGE = PAGE.format(error_css="position: absolute; top: 0;", total_color="#111")

AC3_VISUAL = {
    "route": "checkout.html",
    "viewports": [{"name": "mobile", "width": 390, "height": 844},
                  {"name": "desktop", "width": 1440, "height": 900}],
    "actions": [{"do": "fill", "selector": "#coupon", "value": "EXPIRED"},
                {"do": "click", "selector": "#apply"}],
    "assertions": [
        {"check": "text", "selector": "[data-testid=coupon-error]",
         "value": "This coupon has expired"},
        {"check": "in_viewport", "selector": "[data-testid=coupon-error]"},
        {"check": "in_viewport", "selector": "#apply"},
        {"check": "in_viewport", "selector": "[data-testid=order-total]"},
        {"check": "below", "selector": "[data-testid=coupon-error]", "other": "#coupon"},
        {"check": "no_horizontal_scroll"}],
}


def visual_entry(criterion: str = "AC3", visual: dict | None = None) -> dict:
    return {"criterion_id": criterion, "task": "T1", "fixture": "seeded $100 cart",
            "action": "apply EXPIRED at 390 and 1440", "expected": "message under field",
            "evidence": "visual", "regression_test_name": f"{criterion} expired coupon layout",
            "visual": visual if visual is not None else AC3_VISUAL}


def functional_entry(criterion: str = "AC1", test: str = "test_add") -> dict:
    return {"criterion_id": criterion, "task": "T1", "fixture": "calc", "action": "add",
            "expected": "sum", "evidence": "unit", "regression_test_name": test}


@dataclass
class FakeVision:
    """A vision backend returning a canned verdict and recording what it was asked."""

    verdict: str = "pass"
    provider: str = "local"
    name: str = "fake-vision"
    calls: list[VisionRequest] = field(default_factory=list)

    def available(self) -> bool:
        return True

    def review(self, request: VisionRequest) -> VisionVerdict:
        self.calls.append(request)
        return VisionVerdict(verdict=self.verdict, region="coupon error",
                             evidence=f"{request.criterion_id} at {request.viewport}")


def _cached_browsers() -> Path:
    """The real (not the test HOME's) Playwright browser cache."""
    return Path(pwd.getpwuid(os.getuid()).pw_dir) / "Library" / "Caches" / "ms-playwright"


def _probe() -> str | None:
    """None when chromium launches here, else why the browser tests skip."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "playwright is not installed (pip install 'maggy[visual]')"
    try:
        with sync_playwright() as pw:
            pw.chromium.launch().close()
    except Exception as exc:  # no browsers downloaded, unsupported platform, ...
        return f"chromium cannot launch: {str(exc).splitlines()[0]}"
    return None


@pytest.fixture
def browser() -> None:
    """Point Playwright at the cached browsers and skip when chromium cannot run."""
    if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ and _cached_browsers().is_dir():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_cached_browsers())
    reason = _probe()
    if reason:
        pytest.skip(reason)
