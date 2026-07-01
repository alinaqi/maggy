"""Visual validation for the Maggy dashboard — screenshots with golden-image
comparison, integrated into the normal pytest flow.

A test writes `VisualCheck.snapshot("my-feature")` → compared against
`tests/visual/golden/my-feature.png`. On mismatch the test fails with a diff
path; on missing golden the test writes a candidate and xfails (first-run
bootstrap). Update goldens with `--update-goldens`.

Design draws from Playwright's expect(page).to_have_screenshot() pattern,
adapted to sit naturally in Maggy's TestClient-based test suite.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

_GOLDEN_ROOT = Path(__file__).parent.parent / "tests" / "visual" / "golden"


class VisualMismatchError(AssertionError):
    """Raised when a screenshot doesn't match its golden."""

    def __init__(self, name: str, diff_path: str, diff_pct: float):
        super().__init__(
            f"Visual mismatch for '{name}': {diff_pct:.1f}% pixels differ.\n"
            f"  Diff saved: {diff_path}\n"
            f"  To accept: run with --update-goldens"
        )
        self.name = name
        self.diff_path = diff_path
        self.diff_pct = diff_pct


class NoGoldenError(AssertionError):
    """Raised on first-run when no golden exists — candidate is written."""

    def __init__(self, name: str, candidate_path: str):
        super().__init__(
            f"No golden for '{name}'. Candidate saved at {candidate_path}.\n"
            f"  Review it, then re-run to use it as the golden."
        )
        self.name = name
        self.candidate_path = candidate_path


class VisualCheck:
    """Attach to a Playwright Page to take and verify named screenshots.

    Usage in a test:
        vc = VisualCheck(page, golden_root=...)
        vc.snapshot("sidebar-collapsed", selector="#pane-chat")
    """

    def __init__(
        self,
        page: "Page",
        golden_root: Path | None = None,
    ):
        self._page = page
        self._golden = golden_root or _GOLDEN_ROOT

    # -- public API ----------------------------------------------------------

    def snapshot(
        self, name: str, *, selector: str | None = None, full_page: bool = True,
    ) -> None:
        """Take a screenshot and compare to `tests/visual/golden/<name>.png`.

        Raises VisualMismatchError on diff, NoGoldenError on first-run
        (candidate written). No-op is the golden matches exactly.
        """
        buf = (
            self._page.locator(selector).screenshot()
            if selector
            else self._page.screenshot(full_page=full_page)
        )
        self._check(name, buf)

    def snapshot_viewport(self, name: str) -> None:
        """Take a viewport-only screenshot (no full-page scroll)."""
        self.snapshot(name, full_page=False)

    def snapshot_element(self, name: str, selector: str) -> None:
        """Take a specific element's screenshot."""
        self.snapshot(name, selector=selector, full_page=False)

    # -- internals -----------------------------------------------------------

    def _check(self, name: str, buf: bytes) -> None:
        candidate = self._golden / f"{name}_candidate.png"
        golden = self._golden / f"{name}.png"
        candidate.write_bytes(buf)

        if not golden.exists():
            # first run — keep candidate, ask user to review
            raise NoGoldenError(name, str(candidate))

        if golden.read_bytes() == buf:
            candidate.unlink(missing_ok=True)
            return  # exact match

        diff_path = self._golden / f"{name}_diff.png"
        diff_pct = _pixel_diff(golden, candidate, diff_path)
        if os.environ.get("MAGGY_UPDATE_GOLDENS") or "--update-goldens" in (os.environ.get("PYTEST_ADDOPTS", "")):
            golden.write_bytes(buf)
            candidate.unlink(missing_ok=True)
            diff_path.unlink(missing_ok=True)
            return
        raise VisualMismatchError(name, str(diff_path), diff_pct)


# -- pixel diff (numpy-vectorized; Pillow for IO) ----------------------------

# per-channel delta below this is treated as "same" — absorbs anti-aliasing /
# sub-pixel font rendering noise that would otherwise flag false diffs.
_AA_TOLERANCE = 12


def _pixel_diff(golden_path: Path, candidate_path: Path, diff_path: Path) -> float:
    """Compare two images. Returns % of pixels that differ beyond the
    anti-aliasing tolerance; writes a red-highlighted diff image."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        # fallback: byte-level only (exact or nothing)
        return 100.0 if golden_path.read_bytes() != candidate_path.read_bytes() else 0.0

    a = np.asarray(Image.open(golden_path).convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(candidate_path).convert("RGB"), dtype=np.int16)
    if a.shape != b.shape:
        # size mismatch is a categorical fail; save the candidate for inspection
        Image.open(candidate_path).save(str(diff_path))
        return 100.0

    # a pixel differs if ANY channel exceeds the tolerance
    delta = np.abs(a - b).max(axis=2)
    mask = delta > _AA_TOLERANCE
    pct = float(mask.mean() * 100.0)

    if pct > 0:
        out = np.asarray(Image.open(candidate_path).convert("RGB")).copy()
        out[mask] = (255, 0, 0)  # highlight changed pixels in red
        Image.fromarray(out).save(str(diff_path))
    return pct
