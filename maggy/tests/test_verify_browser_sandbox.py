"""The visual check serves only files that resolve inside the checkout (RFC §2.6.1, 2.6.9):
a symlink committed by the agent must not let the trusted runner render a host file."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.runner.stages.visual_models import VisualSpec
from maggy.runner.verify.browser import inside_checkout, render
from verify_helpers import browser

__all__ = ["browser"]

PAGE = ('<!doctype html><html><body><p id="out">safe</p>'
        '<script src="link.js"></script></body></html>')
LEAK_JS = "document.getElementById('out').textContent = 'LEAKED';"


def _checkout(tmp_path: Path) -> Path:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.js").write_text(LEAK_JS)
    checkout = tmp_path / "co"
    checkout.mkdir()
    (checkout / "index.html").write_text(PAGE)
    (checkout / "own.js").write_text(LEAK_JS)
    (checkout / "link.js").symlink_to(Path("..") / "outside" / "secret.js")
    return checkout


def test_symlink_out_of_the_checkout_is_not_served(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    root = checkout.resolve()
    assert inside_checkout((checkout / "own.js").resolve().as_uri(), root)
    assert not inside_checkout((checkout / "link.js").absolute().as_uri(), root)
    assert not inside_checkout((tmp_path / "outside" / "secret.js").as_uri(), root)
    assert not inside_checkout("https://example.invalid/x.js", root)


@pytest.mark.usefixtures("browser")
def test_rendered_page_cannot_load_a_symlinked_host_file(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    spec = VisualSpec.model_validate({
        "route": "index.html", "viewports": [{"name": "d", "width": 400, "height": 300}],
        "assertions": [{"check": "text", "selector": "#out", "value": "safe"}]})
    [capture] = render(spec, checkout, tmp_path / "out")
    assert capture.image is not None and capture.problems == []
