"""Tests for the council reviewer's diff compressor — invariant: no changed line dropped."""

from __future__ import annotations

from maggy.review.output_filter import compress_patch, is_generated

# A patch with lots of context around a small change.
PATCH = "\n".join([
    "@@ -1,12 +1,12 @@",
    " ctx 1", " ctx 2", " ctx 3", " ctx 4", " ctx 5", " ctx 6",
    "-old line", "+new line",
    " ctx 7", " ctx 8", " ctx 9", " ctx 10", " ctx 11", " ctx 12",
])


class TestCompressPatch:
    def test_keeps_every_changed_line(self):
        out = compress_patch(PATCH, context=2)
        assert "-old line" in out
        assert "+new line" in out

    def test_keeps_hunk_header(self):
        assert "@@ -1,12 +1,12 @@" in compress_patch(PATCH, context=2)

    def test_collapses_far_context(self):
        out = compress_patch(PATCH, context=2)
        assert "hidden" in out                 # a run of context was collapsed
        assert out.count("ctx") < PATCH.count("ctx")  # fewer context lines

    def test_keeps_context_near_changes(self):
        out = compress_patch(PATCH, context=2)
        # the 2 context lines on each side of the change survive
        assert "ctx 6" in out and "ctx 7" in out

    def test_invariant_no_change_line_ever_dropped(self):
        # property check: every +/-/@@ line in any patch survives compression
        big = "@@ -1,40 +1,40 @@\n" + "\n".join(
            ([" same"] * 8 + ["-rm", "+add"]) * 4)
        out = compress_patch(big, context=1)
        for ln in big.splitlines():
            if ln.startswith(("+", "-", "@@")):
                assert ln in out

    def test_short_patch_unchanged(self):
        small = "@@ -1,2 +1,2 @@\n ctx\n-a\n+b\n ctx2"
        assert compress_patch(small, context=3) == small  # nothing to collapse

    def test_empty(self):
        assert compress_patch("") == ""


class TestIsGenerated:
    def test_lockfiles(self):
        assert is_generated("frontend/package-lock.json")
        assert is_generated("Cargo.lock")
        assert is_generated("backend/poetry.lock")

    def test_build_output(self):
        assert is_generated("apps/web/dist/bundle.js")
        assert is_generated("x.min.js")
        assert is_generated("comp/__snapshots__/a.snap")

    def test_real_source_is_not_generated(self):
        assert not is_generated("src/api/routes.py")
        assert not is_generated("lib/auth.ts")


class TestChunkDiffIntegration:
    def test_chunk_diff_compresses_and_stubs(self):
        import pytest
        pytest.importorskip("pydantic_ai")
        from maggy.review.pipeline import chunk_diff_text
        files = [
            {"filename": "src/a.py", "patch": PATCH, "additions": 1, "deletions": 1},
            {"filename": "package-lock.json", "patch": "@@ -1 +1 @@\n-x\n+y", "additions": 1, "deletions": 1},
        ]
        out = chunk_diff_text(files, ["src/a.py", "package-lock.json"])
        assert "-old line" in out and "+new line" in out   # changed lines preserved
        assert "hidden" in out                              # context compressed
        assert "diff omitted" in out                        # lockfile stubbed
