"""Managed JSON / TOML keys: other keys, order, comments preserved."""

from __future__ import annotations

import json

import pytest

from maggy.harness.regions import RegionError, extract, render

USER_JSON = json.dumps({"z": 1, "theme": "dark", "mcp": {"mine": {"cmd": "x"}}}, indent=2) + "\n"

USER_TOML = '''# my codex config
model = "o3"  # inline comment

[profiles.fast]
# keep me
model = "mini"
'''


def test_json_merge_keeps_user_keys_order_and_bytes() -> None:
    out = render("json", USER_JSON, {"mcp.awg": {"command": "awg"}})
    data = json.loads(out)
    assert list(data) == ["z", "theme", "mcp"]
    assert list(data["mcp"]) == ["mine", "awg"]
    assert out.startswith(USER_JSON.split('"mine"')[0])
    assert extract("json", out, ["mcp.awg"]) == {"mcp.awg": json.dumps({"command": "awg"}, indent=2)}


def test_json_unchanged_values_return_original_bytes() -> None:
    odd = '{"a":   1,\n "mcp": {"awg": {"command": "awg"}}}'
    assert render("json", odd, {"mcp.awg": {"command": "awg"}}) == odd


def test_invalid_json_and_jsonc_comments_raise() -> None:
    with pytest.raises(RegionError, match="JSON"):
        render("json", '{"a": 1,,}', {"b": 2})
    with pytest.raises(RegionError, match="JSONC"):
        render("json", '// comment\n{"a": 1}', {"b": 2})


def test_json_root_must_be_object() -> None:
    with pytest.raises(RegionError):
        render("json", "[1, 2]", {"b": 2})


def test_toml_merge_preserves_comments_and_formatting() -> None:
    out = render("toml", USER_TOML, {"mcp_servers.awg": {"command": "awg", "args": ["mcp"]}})
    assert out.startswith(USER_TOML)
    assert "[mcp_servers.awg]" in out
    assert render("toml", out, {"mcp_servers.awg": {"command": "awg", "args": ["mcp"]}}) == out


def test_toml_scalar_key_update_keeps_other_comments() -> None:
    out = render("toml", USER_TOML, {"profiles.fast.model": "big"})
    assert "# my codex config" in out and "# keep me" in out and "# inline comment" in out
    assert extract("toml", out, ["profiles.fast.model"]) == {"profiles.fast.model": '"big"'}


def test_invalid_toml_raises() -> None:
    with pytest.raises(RegionError, match="TOML"):
        render("toml", "model = = 1\n", {"a": 1})
