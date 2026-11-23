"""plan/apply round trip: idempotency, invalid files never clobbered."""

from __future__ import annotations

import json
from pathlib import Path

from harness_engine_helpers import make_ctx, managed, write

from maggy.harness.apply import apply_changes
from maggy.harness.lock import load_lock, region_hash
from maggy.harness.plan import plan_files

TOML = '# codex\nmodel = "o3"  # keep\n'


def _specs(ctx):
    write(ctx.root / "AGENTS.md", "# Mine\n\ntext\n")
    write(ctx.root / "settings.json", json.dumps({"theme": "dark"}, indent=2) + "\n")
    write(ctx.root / "config.toml", TOML)
    return [
        managed(ctx, "AGENTS.md", {"awg": "Use AWG."}),
        managed(ctx, "settings.json", {"hooks.Stop": [{"cmd": "x"}]}),
        managed(ctx, "config.toml", {"mcp_servers.awg": {"command": "awg"}}),
        managed(ctx, "new/opencode.json", {"mcp.awg": {"type": "local"}}),
    ]


def test_apply_twice_second_plan_all_unchanged(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    specs = _specs(ctx)
    first = plan_files(specs, ctx)
    assert [c.kind for c in first] == ["update", "update", "update", "create"]
    report = apply_changes(first, ctx)
    assert len(report.written) == 4
    second = plan_files(specs, ctx)
    assert {(c.kind, c.status) for c in second} == {("unchanged", "ok")}
    assert (ctx.root / "AGENTS.md").read_text().startswith("# Mine\n\ntext\n")
    assert (ctx.root / "config.toml").read_text().startswith(TOML)


def test_lock_records_sha256_of_each_written_region(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    apply_changes(plan_files(_specs(ctx), ctx), ctx)
    entry = load_lock(ctx.lock_path).get(ctx.root / "AGENTS.md", "awg")
    assert entry.sha256 == region_hash("Use AWG.")
    assert entry.content == "Use AWG."


def test_invalid_json_never_overwritten(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    bad = write(ctx.root / "settings.json", '{"theme": "dark",,}')
    [change] = plan_files([managed(ctx, "settings.json", {"a": 1})], ctx)
    assert change.status == "invalid" and "JSON" in change.reason
    report = apply_changes([change], ctx)
    assert bad.read_text() == '{"theme": "dark",,}'
    assert str(bad) in report.skipped and not report.written


def test_invalid_toml_never_overwritten(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    bad = write(ctx.root / "config.toml", "model = = 1\n")
    [change] = plan_files([managed(ctx, "config.toml", {"a": 1})], ctx)
    assert change.status == "invalid"
    apply_changes([change], ctx)
    assert bad.read_text() == "model = = 1\n"


def test_jsonc_with_comments_is_safely_skipped(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    src = write(ctx.root / "opencode.jsonc", '{\n  // mine\n  "a": 1\n}\n')
    [change] = plan_files([managed(ctx, "opencode.jsonc", {"mcp.awg": {}})], ctx)
    assert change.status == "invalid" and "JSONC" in change.reason
    apply_changes([change], ctx)
    assert src.read_text() == '{\n  // mine\n  "a": 1\n}\n'
