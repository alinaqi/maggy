"""Tests for the vendored deterministic review helpers."""

from __future__ import annotations

import pytest

from maggy.review.config import cost_usd
from maggy.review.github import valid_comment_lines
from maggy.review.static_check import _match_changed, _norm


class TestValidCommentLines:
    def test_added_lines_only(self):
        patch = "@@ -1,3 +1,4 @@\n ctx\n-old\n+new1\n+new2\n ctx2"
        assert valid_comment_lines(patch) == {2, 3}

    def test_empty_patch(self):
        assert valid_comment_lines("") == set()

    def test_context_increments_line(self):
        patch = "@@ -1,2 +1,3 @@\n a\n+b\n c"
        assert 2 in valid_comment_lines(patch)  # the added 'b' is new line 2

    def test_no_newline_marker_not_counted(self):
        # "\ No newline at end of file" must not advance the line counter
        patch = "@@ -1,1 +1,2 @@\n a\n+b\n\\ No newline at end of file\n+c"
        # a(ctx)=line1, +b=line2, marker skipped, +c=line3
        assert valid_comment_lines(patch) == {2, 3}


class TestMatchChanged:
    def test_suffix_match_strips_relative_prefix(self):
        changed = {"libs/shared/a.ts", "apps/app/b.py"}
        assert _match_changed("../../libs/shared/a.ts", changed) == "libs/shared/a.ts"

    def test_no_match_returns_none(self):
        assert _match_changed("unrelated/c.ts", {"libs/a.ts"}) is None

    def test_norm_strips_dotdot_and_backslashes(self):
        assert _norm("..\\..\\libs\\a.ts") == "libs/a.ts"


class TestCostUsd:
    def test_unknown_model_is_free(self):
        assert cost_usd("nope", 1000, 1000) == 0.0

    def test_basic_cost(self):
        # gpt-5.5: 15/M in, 120/M out -> 100k in + 10k out = 1.5 + 1.2
        assert round(cost_usd("gpt-5.5", 100_000, 10_000, 0), 3) == 2.7

    def test_cache_discount_applied(self):
        full = cost_usd("gemini-3.5", 100_000, 0, 0)
        cached = cost_usd("gemini-3.5", 100_000, 0, 100_000)
        assert cached < full  # cached input billed at 25%


class TestDecompose:
    def test_small_pr_single_chunk(self):
        pytest.importorskip("pydantic_ai")
        from maggy.review.pipeline import decompose
        files = [{"filename": f"app/a{i}.py"} for i in range(5)]
        assert len(decompose(files, ["python"])) == 1

    def test_large_pr_bounded_chunks(self):
        pytest.importorskip("pydantic_ai")
        from maggy.review.pipeline import MAX_CHUNK_FILES, decompose
        files = [{"filename": f"libs/x/y/z/f{i}.ts"} for i in range(20)]
        chunks = decompose(files, ["typescript"])
        assert len(chunks) > 1
        assert max(len(c.files) for c in chunks) <= MAX_CHUNK_FILES
