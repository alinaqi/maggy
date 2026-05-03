"""Tests for cross-tool (Claude/Kimi/Codex) compatibility."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


class TestDetectAgents:
    """Tests for scripts/detect-agents.sh."""

    def test_script_exists_and_executable(self) -> None:
        script = REPO_ROOT / "scripts" / "detect-agents.sh"
        assert script.exists()
        assert os.access(script, os.X_OK)

    def test_outputs_valid_format(self) -> None:
        script = REPO_ROOT / "scripts" / "detect-agents.sh"
        result = subprocess.run(
            [str(script)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        valid_tools = {"claude", "kimi", "codex"}
        for line in result.stdout.strip().splitlines():
            assert line in valid_tools


class TestInstallSkills:
    """Tests for scripts/install-skills.sh."""

    def test_script_exists_and_executable(self) -> None:
        script = REPO_ROOT / "scripts" / "install-skills.sh"
        assert script.exists()
        assert os.access(script, os.X_OK)

    def test_copies_skills_to_target(self, tmp_path: Path) -> None:
        script = REPO_ROOT / "scripts" / "install-skills.sh"
        target = tmp_path / "target-skills"

        result = subprocess.run(
            [str(script), str(target)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert target.exists()

        # Should have at least 'base' skill
        base_skill = target / "base" / "SKILL.md"
        assert base_skill.exists()

    def test_no_args_shows_usage(self) -> None:
        script = REPO_ROOT / "scripts" / "install-skills.sh"
        result = subprocess.run(
            [str(script)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0


class TestTemplates:
    """Tests for cross-tool templates."""

    def test_agents_md_exists(self) -> None:
        path = REPO_ROOT / "templates" / "AGENTS.md"
        assert path.exists()

    def test_agents_md_has_skills_section(self) -> None:
        path = REPO_ROOT / "templates" / "AGENTS.md"
        content = path.read_text()
        assert "## Skills" in content
        assert "SKILL.md" in content

    def test_config_toml_exists(self) -> None:
        path = REPO_ROOT / "templates" / "config.toml"
        assert path.exists()

    def test_config_toml_has_hooks(self) -> None:
        path = REPO_ROOT / "templates" / "config.toml"
        content = path.read_text()
        assert "[[hooks]]" in content
        assert 'event = "Stop"' in content
        assert 'event = "SessionStart"' in content

    def test_agents_md_has_conventions(self) -> None:
        path = REPO_ROOT / "templates" / "AGENTS.md"
        content = path.read_text()
        assert "## Conventions" in content
        assert "## Don't" in content


class TestSyncAgentsCommand:
    """Tests for commands/sync-agents.md."""

    def test_command_exists(self) -> None:
        path = REPO_ROOT / "commands" / "sync-agents.md"
        assert path.exists()

    def test_command_has_phases(self) -> None:
        path = REPO_ROOT / "commands" / "sync-agents.md"
        content = path.read_text()
        assert "## Phase 1" in content
        assert "## Phase 2" in content
        assert "detect-agents.sh" in content
