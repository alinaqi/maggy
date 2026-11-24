"""Fake AI CLI binaries for cli_discovery tests."""

from __future__ import annotations

from pathlib import Path

import pytest

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
