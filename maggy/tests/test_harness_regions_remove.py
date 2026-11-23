"""Removing a managed region (REMOVE) from Markdown and TOML files."""

from __future__ import annotations

import tomllib

from maggy.harness.regions import REMOVE, extract, render

BLOCK = "<!-- maggy:begin awg -->\nAWG\n<!-- maggy:end awg -->"


def test_markdown_block_removed_and_other_bytes_kept() -> None:
    text = f"# Mine\n\n{BLOCK}\n\ntail\n"
    out = render("markdown", text, {"awg": REMOVE})
    assert out == "# Mine\n\ntail\n"
    assert extract("markdown", out, ["awg"]) == {"awg": None}


def test_appended_block_removal_restores_the_original() -> None:
    original = "# Mine\n"
    added = render("markdown", original, {"awg": "AWG"})
    assert render("markdown", added, {"awg": REMOVE}) == original


def test_absent_block_removal_is_a_noop() -> None:
    assert render("markdown", "# Mine\n", {"awg": REMOVE}) == "# Mine\n"
    assert render("markdown", None, {"awg": REMOVE}) == ""


def test_toml_table_removed_and_comments_kept() -> None:
    text = '# mine\nmodel = "o3"\n\n[mcp_servers.awg]\ncommand = "awg"\n\n[mcp_servers.other]\ncommand = "x"\n'
    out = render("toml", text, {"mcp_servers.awg": REMOVE})
    assert out.startswith('# mine\nmodel = "o3"\n')
    assert tomllib.loads(out)["mcp_servers"] == {"other": {"command": "x"}}
    assert render("toml", out, {"mcp_servers.awg": REMOVE}) == out
