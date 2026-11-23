"""Managed text blocks: markers, insertion, byte-for-byte preservation."""

from __future__ import annotations

import pytest

from maggy.harness.regions import RegionError, extract, render

USER_MD = "# My notes\n\nKeep   this\twhitespace.\n\n<!-- my comment -->\nno trailing newline"


def test_block_appended_when_absent_and_user_text_untouched() -> None:
    out = render("markdown", USER_MD, {"awg": "Use AWG."})
    assert out.startswith(USER_MD)
    assert out.endswith("<!-- maggy:begin awg -->\nUse AWG.\n<!-- maggy:end awg -->\n")


def test_replacing_block_preserves_outside_bytes() -> None:
    first = render("markdown", USER_MD, {"awg": "old"})
    tail = "\n\n## After block\n  indented\n"
    second = render("markdown", first + tail, {"awg": "new\nlines"})
    head, _, rest = second.partition("<!-- maggy:begin awg -->")
    assert head == first.partition("<!-- maggy:begin awg -->")[0]
    assert rest.endswith("<!-- maggy:end awg -->\n" + tail)
    assert extract("markdown", second, ["awg"]) == {"awg": "new\nlines"}


def test_render_is_idempotent() -> None:
    once = render("markdown", USER_MD, {"a": "x", "b": "y"})
    assert render("markdown", once, {"a": "x", "b": "y"}) == once


def test_new_file_gets_only_the_block() -> None:
    assert render("markdown", None, {"a": "x"}) == "<!-- maggy:begin a -->\nx\n<!-- maggy:end a -->\n"


def test_hash_comment_style_for_text_configs() -> None:
    out = render("text", "key = 1\n", {"awg": "x = 2"})
    assert out == "key = 1\n\n# maggy:begin awg\nx = 2\n# maggy:end awg\n"
    assert extract("text", out, ["awg", "missing"]) == {"awg": "x = 2", "missing": None}


def test_begin_without_end_is_malformed() -> None:
    with pytest.raises(RegionError, match="awg"):
        render("markdown", "<!-- maggy:begin awg -->\nhalf\n", {"awg": "x"})
