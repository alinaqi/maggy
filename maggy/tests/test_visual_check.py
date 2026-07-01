"""Unit tests for VisualCheck core logic — pixel diff + golden lifecycle.

These run in plain pytest (no browser): a fake "page" yields PNG bytes, so the
golden-management and diff logic is fully testable without Playwright.
"""

from __future__ import annotations

import io

import pytest

from maggy.visual_check import (
    NoGoldenError,
    VisualCheck,
    VisualMismatchError,
    _pixel_diff,
)

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402


def _png(color, size=(40, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


class _FakePage:
    """Stands in for a Playwright Page — returns canned PNG bytes."""

    def __init__(self, png: bytes):
        self._png = png

    def screenshot(self, **_kw) -> bytes:
        return self._png

    def locator(self, _sel):
        return self

    def set_default_timeout(self, _ms):
        pass


@pytest.fixture()
def golden_dir(tmp_path):
    d = tmp_path / "golden"
    d.mkdir()
    return d


class TestFirstRun:
    def test_missing_golden_writes_candidate_and_raises(self, golden_dir):
        vc = VisualCheck(_FakePage(_png("red")), golden_root=golden_dir)
        with pytest.raises(NoGoldenError):
            vc.snapshot("hero")
        assert (golden_dir / "hero_candidate.png").exists()


class TestMatch:
    def test_identical_passes(self, golden_dir):
        png = _png("blue")
        (golden_dir / "hero.png").write_bytes(png)
        vc = VisualCheck(_FakePage(png), golden_root=golden_dir)
        vc.snapshot("hero")  # no raise = pass
        assert not (golden_dir / "hero_candidate.png").exists()  # cleaned up


class TestMismatch:
    def test_different_raises_with_diff(self, golden_dir):
        (golden_dir / "hero.png").write_bytes(_png("blue"))
        vc = VisualCheck(_FakePage(_png("red")), golden_root=golden_dir)
        with pytest.raises(VisualMismatchError) as exc:
            vc.snapshot("hero")
        assert exc.value.diff_pct > 0
        assert (golden_dir / "hero_diff.png").exists()

    def test_update_goldens_accepts(self, golden_dir, monkeypatch):
        (golden_dir / "hero.png").write_bytes(_png("blue"))
        monkeypatch.setenv("MAGGY_UPDATE_GOLDENS", "1")
        new = _png("red")
        vc = VisualCheck(_FakePage(new), golden_root=golden_dir)
        vc.snapshot("hero")  # no raise — golden updated
        assert (golden_dir / "hero.png").read_bytes() == new


class TestPixelDiff:
    def test_identical_zero_pct(self, golden_dir):
        a = golden_dir / "a.png"
        b = golden_dir / "b.png"
        a.write_bytes(_png("green"))
        b.write_bytes(_png("green"))
        assert _pixel_diff(a, b, golden_dir / "d.png") == 0.0

    def test_fully_different_100_pct(self, golden_dir):
        a = golden_dir / "a.png"
        b = golden_dir / "b.png"
        a.write_bytes(_png("black"))
        b.write_bytes(_png("white"))
        assert _pixel_diff(a, b, golden_dir / "d.png") == 100.0

    def test_size_mismatch_is_100(self, golden_dir):
        a = golden_dir / "a.png"
        b = golden_dir / "b.png"
        a.write_bytes(_png("blue", size=(40, 30)))
        b.write_bytes(_png("blue", size=(80, 60)))
        assert _pixel_diff(a, b, golden_dir / "d.png") == 100.0

    def test_partial_diff_between_0_and_100(self, golden_dir):
        # half red, half blue vs all blue → ~50% differ
        img = Image.new("RGB", (40, 30), "blue")
        for x in range(20):
            for y in range(30):
                img.putpixel((x, y), (255, 0, 0))
        a = golden_dir / "a.png"
        b = golden_dir / "b.png"
        img.save(str(a))
        Image.new("RGB", (40, 30), "blue").save(str(b))
        pct = _pixel_diff(a, b, golden_dir / "d.png")
        assert 40 < pct < 60
