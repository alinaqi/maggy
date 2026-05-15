"""Tests for scope tag inference and comparison."""

from maggy.mnemos.scope import infer_scope_tags, merge_scope_tags, scope_overlap


class TestInferScopeTags:
    def test_nested_path(self):
        tags = infer_scope_tags("src/auth/login.py")
        assert tags == ["src", "auth"]

    def test_single_file(self):
        tags = infer_scope_tags("main.py")
        assert tags == []

    def test_empty_path(self):
        assert infer_scope_tags("") == []

    def test_deep_path_capped(self):
        tags = infer_scope_tags("a/b/c/d/e/f/g.py")
        assert len(tags) <= 5


class TestMergeScopeTags:
    def test_merge_unique(self):
        result = merge_scope_tags(["a", "b"], ["c"])
        assert result == ["a", "b", "c"]

    def test_merge_dedup(self):
        result = merge_scope_tags(["a", "b"], ["b", "c"])
        assert result == ["a", "b", "c"]

    def test_merge_empty(self):
        assert merge_scope_tags([], ["x"]) == ["x"]


class TestScopeOverlap:
    def test_identical(self):
        assert scope_overlap(["a", "b"], ["a", "b"]) == 1.0

    def test_disjoint(self):
        assert scope_overlap(["a"], ["b"]) == 0.0

    def test_partial(self):
        o = scope_overlap(["a", "b"], ["b", "c"])
        assert 0.3 < o < 0.4  # 1/3

    def test_both_empty(self):
        assert scope_overlap([], []) == 1.0
