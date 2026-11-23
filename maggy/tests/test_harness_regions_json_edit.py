"""JSON managed keys are edited in place: bytes outside them are never rewritten."""

from __future__ import annotations

import json

import pytest

from maggy.harness.regions import REMOVE, RegionError, render

ODD = '{\n  "theme": "dark",\n  "list": [1, 2, 3],\n  "url": "a\\/b",\n  "mcpServers": {"x": 1}\n}\n'


def test_new_nested_key_keeps_inline_arrays_and_escapes() -> None:
    out = render("json", ODD, {"mcpServers.awg": {"command": "awg"}})
    assert '"list": [1, 2, 3],' in out and '"url": "a\\/b",' in out
    assert json.loads(out)["mcpServers"] == {"x": 1, "awg": {"command": "awg"}}
    assert out.startswith('{\n  "theme": "dark",\n  "list": [1, 2, 3],\n  "url": "a\\/b",\n')


def test_replaced_value_touches_only_its_own_bytes() -> None:
    out = render("json", ODD, {"theme": ["a", "b"]})
    assert out.replace('[\n    "a",\n    "b"\n  ]', '"dark"') == ODD


def test_missing_parents_are_created_inside_the_root_object() -> None:
    out = render("json", ODD, {"permissions.allow": ["Bash"]})
    assert out.startswith(ODD.rstrip()[:-1].rstrip())
    assert json.loads(out)["permissions"] == {"allow": ["Bash"]}
    assert '"list": [1, 2, 3]' in out and out.endswith("}\n")


def test_insert_into_empty_object_and_into_empty_file() -> None:
    assert json.loads(render("json", "{}\n", {"a.b": 1})) == {"a": {"b": 1}}
    assert render("json", None, {"a": 1}) == '{\n  "a": 1\n}\n'


def test_remove_key_keeps_siblings_bytes() -> None:
    out = render("json", ODD, {"list": REMOVE})
    assert out == '{\n  "theme": "dark",\n  "url": "a\\/b",\n  "mcpServers": {"x": 1}\n}\n'
    last = render("json", ODD, {"mcpServers": REMOVE})
    assert last == '{\n  "theme": "dark",\n  "list": [1, 2, 3],\n  "url": "a\\/b"\n}\n'
    assert json.loads(render("json", '{"only": 1}', {"only": REMOVE})) == {}


def test_remove_absent_key_is_a_noop() -> None:
    assert render("json", ODD, {"nope.deeper": REMOVE}) == ODD


def test_parent_that_is_not_an_object_raises() -> None:
    with pytest.raises(RegionError, match="not an object"):
        render("json", ODD, {"list.x": 1})


def test_tabs_and_crlf_files_keep_their_layout() -> None:
    text = '{\r\n\t"a": [1,2],\r\n\t"b": {}\r\n}'
    out = render("json", text, {"b.c": True})
    assert out.startswith('{\r\n\t"a": [1,2],\r\n') and json.loads(out) == {"a": [1, 2], "b": {"c": True}}
