"""Prompt assembly — combines stable, context, and volatile layers."""

from __future__ import annotations

from maggy.prompt.context_layer import (
    claude_md_section,
    file_tree_section,
    git_state_section,
    mode_section,
    tech_stack_section,
)
from maggy.prompt.modes import Mode, detect_mode
from maggy.prompt.sections import (
    PromptSection,
    capabilities_section,
    identity_section,
    mode_semantics_section,
    render_sections,
    rules_section,
    safety_section,
)
from maggy.prompt.skill_index import skill_index_section

_FALLBACK = (
    "You are Maggy, an autonomous AI engineering assistant.\n"
    "Help with coding, debugging, research, planning, "
    "architecture, and any engineering task.\n"
    "Be concise. Read code before answering code questions."
)


class PromptAssemblyService:
    def assemble(
        self, working_dir: str, project_key: str,
    ) -> str:
        try:
            sections = self._stable_sections(project_key)
            sections += self._context_sections(working_dir)
            sections += self._skill_sections(
                working_dir, project_key,
            )
            return render_sections(sections)
        except Exception:
            return _FALLBACK

    def _stable_sections(
        self, project_key: str,
    ) -> list[PromptSection]:
        return [
            identity_section(project_key),
            capabilities_section(),
            rules_section(),
            mode_semantics_section(),
            safety_section(),
        ]

    def _context_sections(
        self, working_dir: str,
    ) -> list[PromptSection]:
        detected = detect_mode(working_dir)
        sections = [mode_section(detected)]
        if detected.mode == Mode.BOOTSTRAP:
            sections.append(self._bootstrap_hint(working_dir))
            return sections
        sections.append(file_tree_section(working_dir))
        sections.append(git_state_section(working_dir))
        sections.append(tech_stack_section(working_dir))
        sections.append(claude_md_section(working_dir))
        sections.append(self._working_dir_section(working_dir))
        return sections

    def _bootstrap_hint(
        self, working_dir: str,
    ) -> PromptSection:
        return PromptSection(
            id="bootstrap_hint",
            layer="context",
            content=(
                "## Bootstrap Mode\n"
                "No project detected. Help the user scaffold, "
                "clone, or research before coding."
            ),
            priority=14,
        )

    def _skill_sections(
        self, working_dir: str, project_key: str,
    ) -> list[PromptSection]:
        try:
            from maggy.skills.injector import match_skills
            from maggy.skills.registry import SkillRegistry
            reg = SkillRegistry()
            reg.load_global()
            if project_key:
                reg.load_project(project_key, working_dir)
            skills = reg.resolve(project_key or None)
            matched = match_skills(skills, working_dir)
            section = skill_index_section(matched)
            return [section] if section.content else []
        except Exception:
            return []

    def _working_dir_section(
        self, working_dir: str,
    ) -> PromptSection:
        return PromptSection(
            id="working_dir",
            layer="context",
            content=f"Working directory: `{working_dir}`",
            priority=15,
        )
