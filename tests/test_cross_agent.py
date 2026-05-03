"""Tests for cross-agent intelligence (Codex auto-review, Kimi delegation, iCPG + Mnemos)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


class TestCodexAutoReview:
    """Tests for templates/codex-auto-review.sh."""

    def test_script_exists(self) -> None:
        path = REPO_ROOT / "templates" / "codex-auto-review.sh"
        assert path.exists()

    def test_script_is_executable(self) -> None:
        path = REPO_ROOT / "templates" / "codex-auto-review.sh"
        assert os.access(path, os.X_OK)

    def test_script_has_shebang(self) -> None:
        path = REPO_ROOT / "templates" / "codex-auto-review.sh"
        content = path.read_text()
        assert content.startswith("#!/bin/bash")

    def test_script_checks_codex_installed(self) -> None:
        path = REPO_ROOT / "templates" / "codex-auto-review.sh"
        content = path.read_text()
        assert "command -v codex" in content

    def test_script_uses_exit_codes(self) -> None:
        path = REPO_ROOT / "templates" / "codex-auto-review.sh"
        content = path.read_text()
        assert "exit 0" in content
        assert "return 2" in content


class TestCrossAgentDelegation:
    """Tests for skills/cross-agent-delegation/SKILL.md."""

    def test_skill_exists(self) -> None:
        path = REPO_ROOT / "skills" / "cross-agent-delegation" / "SKILL.md"
        assert path.exists()

    def test_skill_has_frontmatter(self) -> None:
        path = REPO_ROOT / "skills" / "cross-agent-delegation" / "SKILL.md"
        content = path.read_text()
        assert content.startswith("---")
        assert "name: cross-agent-delegation" in content

    def test_skill_references_icpg(self) -> None:
        path = REPO_ROOT / "skills" / "cross-agent-delegation" / "SKILL.md"
        content = path.read_text()
        assert "icpg" in content.lower()
        assert "icpg query prior" in content
        assert "icpg query constraints" in content
        assert "icpg query risk" in content

    def test_skill_references_mnemos(self) -> None:
        path = REPO_ROOT / "skills" / "cross-agent-delegation" / "SKILL.md"
        content = path.read_text()
        assert "mnemos" in content.lower()
        assert "mnemos add goal" in content
        assert "mnemos checkpoint" in content

    def test_skill_has_blast_radius_rules(self) -> None:
        path = REPO_ROOT / "skills" / "cross-agent-delegation" / "SKILL.md"
        content = path.read_text()
        assert "Blast Radius" in content or "blast radius" in content
        assert "1-3 files" in content
        assert "4-8 files" in content
        assert "9+ files" in content

    def test_skill_has_tool_detection(self) -> None:
        path = REPO_ROOT / "skills" / "cross-agent-delegation" / "SKILL.md"
        content = path.read_text()
        assert "command -v kimi" in content
        assert "command -v codex" in content


class TestSettingsJsonHook:
    """Tests for codex-auto-review hook in settings.json."""

    def test_settings_has_codex_review_hook(self) -> None:
        path = REPO_ROOT / "templates" / "settings.json"
        data = json.loads(path.read_text())
        stop_hooks = data["hooks"]["Stop"][0]["hooks"]
        commands = [h["command"] for h in stop_hooks]
        assert any("codex-auto-review" in cmd for cmd in commands)

    def test_codex_hook_after_tdd(self) -> None:
        path = REPO_ROOT / "templates" / "settings.json"
        data = json.loads(path.read_text())
        stop_hooks = data["hooks"]["Stop"][0]["hooks"]
        commands = [h["command"] for h in stop_hooks]
        tdd_idx = next(
            i for i, c in enumerate(commands) if "tdd-loop-check" in c
        )
        codex_idx = next(
            i for i, c in enumerate(commands) if "codex-auto-review" in c
        )
        assert codex_idx > tdd_idx

    def test_codex_hook_before_icpg(self) -> None:
        path = REPO_ROOT / "templates" / "settings.json"
        data = json.loads(path.read_text())
        stop_hooks = data["hooks"]["Stop"][0]["hooks"]
        commands = [h["command"] for h in stop_hooks]
        codex_idx = next(
            i for i, c in enumerate(commands) if "codex-auto-review" in c
        )
        icpg_idx = next(
            i for i, c in enumerate(commands) if "icpg-stop-record" in c
        )
        assert codex_idx < icpg_idx

    def test_codex_hook_has_timeout(self) -> None:
        path = REPO_ROOT / "templates" / "settings.json"
        data = json.loads(path.read_text())
        stop_hooks = data["hooks"]["Stop"][0]["hooks"]
        codex_hook = next(
            h for h in stop_hooks if "codex-auto-review" in h["command"]
        )
        assert codex_hook["timeout"] == 120


class TestConfigTomlHook:
    """Tests for codex-auto-review hook in config.toml."""

    def test_config_toml_has_codex_hook(self) -> None:
        path = REPO_ROOT / "templates" / "config.toml"
        content = path.read_text()
        assert "codex-auto-review" in content

    def test_config_toml_codex_hook_timeout(self) -> None:
        path = REPO_ROOT / "templates" / "config.toml"
        content = path.read_text()
        # Find the codex-auto-review block and check timeout
        lines = content.splitlines()
        in_codex_block = False
        for line in lines:
            if "Codex Auto-Review" in line:
                in_codex_block = True
            if in_codex_block and line.startswith("timeout"):
                assert "120" in line
                break


class TestTemplateSkillRefs:
    """Tests for skill references in templates."""

    def test_claude_md_has_delegation_skill(self) -> None:
        path = REPO_ROOT / "templates" / "CLAUDE.md"
        content = path.read_text()
        assert "cross-agent-delegation/SKILL.md" in content

    def test_agents_md_has_delegation_skill(self) -> None:
        path = REPO_ROOT / "templates" / "AGENTS.md"
        content = path.read_text()
        assert "cross-agent-delegation/SKILL.md" in content

    def test_claude_md_has_workflow_section(self) -> None:
        path = REPO_ROOT / "templates" / "CLAUDE.md"
        content = path.read_text()
        assert "## Cross-Agent Workflow" in content
        assert "Codex Auto-Review" in content
        assert "Kimi Delegation" in content

    def test_agents_md_has_workflow_section(self) -> None:
        path = REPO_ROOT / "templates" / "AGENTS.md"
        content = path.read_text()
        assert "## Cross-Agent Workflow" in content
        assert "Codex Auto-Review" in content
        assert "Kimi Delegation" in content


class TestInitializeProjectRef:
    """Tests for cross-agent-delegation in initialize-project.md."""

    def test_init_copies_delegation_skill(self) -> None:
        path = REPO_ROOT / "commands" / "initialize-project.md"
        content = path.read_text()
        assert "cross-agent-delegation/" in content
