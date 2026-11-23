"""Tests for CLI auto-discovery and command building."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.adapters.cli_discovery import (
    CliProfile,
    discover_all,
    discover_cli,
)

# Discovery probes real binaries with --help. These fakes reproduce the flag
# lines of each CLI's help output so the tests do not depend on which AI CLIs
# happen to be installed on the machine running them.
_FAKE_HELP = {
    "claude": {
        "": "Usage: claude [options] [prompt]\n"
            "  -p, --print  Print response and exit\n"
            "  --output-format <format>  text, json, stream-json\n"
            "  --dangerously-skip-permissions  Bypass permission checks\n"
            "  --max-turns <n>  Maximum agentic turns",
    },
    "codex": {
        "": "Usage: codex [OPTIONS] [PROMPT]\n"
            "Commands:\n"
            "  exec  Run Codex non-interactively\n"
            "  -p, --profile <PROFILE>  Config profile",
        "exec": "Usage: codex exec [OPTIONS] [PROMPT]\n"
                "  -C, --cd <DIR>  Working root\n"
                "  --dangerously-bypass-approvals-and-sandbox  Skip prompts",
    },
    "kimi": {
        "": "Usage: kimi [OPTIONS]\n"
            "  -p, --prompt TEXT  User prompt\n"
            "  -w, --work-dir PATH  Working directory\n"
            "  --yolo  Automatically approve all actions\n"
            "  --afk  Away-from-keyboard mode\n"
            "  --max-steps-per-turn INTEGER  Step limit",
    },
    "ollama": {
        "": "Usage: ollama [command]\n"
            "Available Commands:\n"
            "  serve       Start ollama\n"
            "  run         Run a model\n"
            "  list        List models",
        "run": "Usage: ollama run MODEL [PROMPT] [flags]",
        "list": "NAME                        ID      SIZE\n"
                "qwen3-coder:30b-a3b-q8_0    abc123  32 GB",
    },
}


def _fake_cli(bin_dir: Path, name: str, outputs: dict[str, str]) -> None:
    lines = ["#!/bin/sh", 'case "$1" in',
             f'  --version|-V|-v) echo "{name} 1.0.0" ;;']
    for sub, text in outputs.items():
        if sub:
            lines.append(f"  {sub}) printf '%s\\n' '{text}' ;;")
    lines += [f"  *) printf '%s\\n' '{outputs['']}' ;;", "esac"]
    exe = bin_dir / name
    exe.write_text("\n".join(lines) + "\n")
    exe.chmod(0o755)


@pytest.fixture(autouse=True)
def fake_clis(tmp_path: Path, monkeypatch) -> Path:
    """PATH holds only the fake claude/codex/kimi/ollama binaries."""
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    for name, outputs in _FAKE_HELP.items():
        _fake_cli(bin_dir, name, outputs)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    return bin_dir


def test_discover_all_returns_profiles():
    result = discover_all()
    assert "claude" in result.profiles
    assert "codex" in result.profiles
    assert "kimi" in result.profiles


def test_claude_discovered():
    p = discover_cli("claude")
    assert p.installed is True
    assert p.prompt_is_positional is True
    assert p.prompt_flag == "-p"
    assert "skip-permissions" in p.auto_approve_flag
    assert p.output_format_flag == "--output-format"
    assert p.work_dir_flag == ""


def test_codex_discovered():
    p = discover_cli("codex")
    assert p.installed is True
    assert p.uses_exec_subcommand is True
    assert p.prompt_is_positional is True
    assert "bypass" in p.auto_approve_flag
    assert p.work_dir_flag == "-C"


def test_kimi_discovered():
    p = discover_cli("kimi")
    assert p.installed is True
    assert p.prompt_flag == "-p"
    assert p.auto_approve_flag == "--yolo"
    assert p.afk_flag == "--afk"
    assert p.work_dir_flag == "-w"


def test_missing_cli():
    p = discover_cli("nonexistent_xyz")
    assert p.installed is False


def test_claude_build_command():
    p = CliProfile(
        name="claude", binary="claude", installed=True,
        prompt_flag="-p", prompt_is_positional=True,
        auto_approve_flag="--dangerously-skip-permissions",
        output_format_flag="--output-format",
    )
    cmd = p.build_command("do stuff", "/tmp/repo", 20)
    assert cmd[:3] == ["claude", "-p", "do stuff"]
    assert "--dangerously-skip-permissions" in cmd
    assert "--output-format" in cmd
    assert "json" in cmd


def test_codex_build_command():
    p = CliProfile(
        name="codex", binary="codex", installed=True,
        uses_exec_subcommand=True, prompt_is_positional=True,
        work_dir_flag="-C",
        auto_approve_flag="--dangerously-bypass-approvals-and-sandbox",
    )
    cmd = p.build_command("do stuff", "/tmp/repo", 10)
    assert cmd[:3] == ["codex", "exec", "do stuff"]
    assert "-C" in cmd
    assert "/tmp/repo" in cmd


def test_kimi_build_command():
    p = CliProfile(
        name="kimi", binary="kimi", installed=True,
        prompt_flag="-p", work_dir_flag="-w",
        auto_approve_flag="--yolo", afk_flag="--afk",
    )
    cmd = p.build_command("do stuff", "/tmp/repo", 10)
    assert cmd[:3] == ["kimi", "-p", "do stuff"]
    assert "-w" in cmd
    assert "--yolo" in cmd
    assert "--afk" in cmd


def test_ollama_discovered():
    p = discover_cli("ollama")
    assert p.installed is True
    assert p.uses_run_subcommand is True
    assert p.prompt_is_positional is True
    assert "qwen" in p.run_model and "coder" in p.run_model


def test_ollama_build_command():
    p = CliProfile(
        name="ollama", binary="ollama", installed=True,
        uses_run_subcommand=True, run_model="qwen3-coder:30b-a3b-q8_0",
        prompt_is_positional=True,
    )
    cmd = p.build_command("do stuff", "/tmp/repo", 5)
    assert cmd[:4] == ["ollama", "run", "qwen3-coder:30b-a3b-q8_0", "do stuff"]
    assert "--output-format" not in cmd


def test_pi_adapter_uses_discovery():
    from maggy.adapters.pi import PiAdapter
    pi = PiAdapter()
    profiles = pi.discovered_profiles
    assert "claude" in profiles
    assert profiles["claude"].installed is True
    assert "ollama" in profiles
    assert profiles["ollama"].installed is True
