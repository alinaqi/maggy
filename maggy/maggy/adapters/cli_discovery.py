"""Auto-discover installed AI CLIs and their command-line flags.

Probes each CLI via --help, parses capabilities, and builds
command templates that PiAdapter uses to spawn prompts.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field

from maggy.adapters.cli_probe import detect_ollama_model, get_help, get_version


@dataclass
class CliProfile:
    """Discovered CLI capabilities and flags."""

    name: str
    binary: str
    version: str = ""
    installed: bool = False
    prompt_flag: str = ""
    work_dir_flag: str = ""
    auto_approve_flag: str = ""
    output_format_flag: str = ""
    max_turns_flag: str = ""
    afk_flag: str = ""
    uses_exec_subcommand: bool = False
    uses_run_subcommand: bool = False
    run_model: str = ""
    prompt_is_positional: bool = False

    def build_command(
        self, prompt: str, wd: str, max_turns: int,
    ) -> list[str]:
        """Build full CLI command from discovered flags."""
        cmd = [self.binary, *self._subcommand()]
        cmd += [self.prompt_flag, prompt] if self.prompt_flag else [prompt]
        if self.work_dir_flag:
            cmd += [self.work_dir_flag, wd]
        cmd += [f for f in (self.auto_approve_flag, self.afk_flag) if f]
        if self.output_format_flag:
            cmd += [self.output_format_flag, "json"]
        if self.max_turns_flag and max_turns > 0:
            cmd += [self.max_turns_flag, str(max_turns)]
        return cmd

    def _subcommand(self) -> list[str]:
        """Leading subcommand: `exec` (codex) or `run <model>` (ollama)."""
        if self.uses_exec_subcommand:
            return ["exec"]
        if self.uses_run_subcommand:
            return ["run", self.run_model]
        return []


@dataclass
class DiscoveryResult:
    """Result of scanning all known CLI tools."""

    profiles: dict[str, CliProfile] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


_KNOWN_CLIS = ["claude", "codex", "kimi", "deepseek", "ollama"]


def discover_all() -> DiscoveryResult:
    """Scan for all known AI CLIs and probe capabilities."""
    result = DiscoveryResult()
    for name in _KNOWN_CLIS:
        profile = discover_cli(name)
        result.profiles[name] = profile
        if not profile.installed:
            result.errors.append(f"{name}: not found")
    return result


def discover_cli(name: str) -> CliProfile:
    """Probe a single CLI binary for capabilities."""
    binary = shutil.which(name)
    if not binary:
        return CliProfile(name=name, binary=name)
    profile = CliProfile(name=name, binary=binary, installed=True)
    profile.version = get_version(binary)
    _extract_flags(profile, get_help(binary, ""))
    if profile.uses_exec_subcommand:
        _refine_from_exec(profile, get_help(binary, "exec"))
    if profile.uses_run_subcommand:
        _refine_from_run(profile)
    _post_process(profile)
    return profile


# (profile attribute, [(help-text pattern, value), ...]); first match wins.
# auto_approve_flag stays: PiAdapter (and the executor through it) builds
# unpinned claude/codex commands from these profiles and relies on it.
_FLAG_RULES: list[tuple[str, list[tuple[str, object]]]] = [
    ("prompt_flag", [(r"-p,\s*--print\b", "--print"), (r"(-p|--prompt)\b", "-p")]),
    ("work_dir_flag", [
        (r"--work-dir\b", "-w"), (r"-C,\s*--cd\b", "-C"), (r"--cwd\b", "--cwd"),
    ]),
    ("auto_approve_flag", [
        (r"--dangerously-skip-permissions\b", "--dangerously-skip-permissions"),
        (r"--dangerously-bypass-approvals", "--dangerously-bypass-approvals-and-sandbox"),
        (r"--yolo\b", "--yolo"),
        (r"--auto-approve\b", "--auto-approve"),
    ]),
    ("output_format_flag", [(r"--output-format\b", "--output-format")]),
    ("max_turns_flag", [
        (r"--max-turns\b", "--max-turns"),
        (r"--max-steps-per", "--max-steps-per-turn"),
        (r"--max-steps\b", "--max-steps"),
    ]),
    ("afk_flag", [(r"--afk\b", "--afk")]),
    ("uses_exec_subcommand", [(r"\bexec\b.*non-interactive", True)]),
    ("uses_run_subcommand", [(r"\brun\s+Run a model\b", True)]),
]


def _extract_flags(profile: CliProfile, text: str) -> None:
    """Extract flags by matching known flag names in help."""
    for attr, rules in _FLAG_RULES:
        value = next((v for pat, v in rules if _has(text, pat)), None)
        if value is not None:
            setattr(profile, attr, value)


def _refine_from_exec(profile: CliProfile, text: str) -> None:
    """Override flags with more specific exec subcommand flags."""
    if _has(text, r"-C,\s*--cd\b"):
        profile.work_dir_flag = "-C"
    if _has(text, r"--dangerously-bypass-approvals"):
        profile.auto_approve_flag = "--dangerously-bypass-approvals-and-sandbox"


def _refine_from_run(profile: CliProfile) -> None:
    """Run subcommand (ollama-style): prompt is positional, model needed."""
    profile.prompt_is_positional = True
    profile.prompt_flag = ""
    if not profile.run_model:
        profile.run_model = detect_ollama_model(profile.binary)


def _post_process(profile: CliProfile) -> None:
    """Apply heuristics after flag extraction."""
    # --print means non-interactive mode; prompt is positional
    if profile.prompt_flag == "--print":
        profile.prompt_is_positional = True
        profile.prompt_flag = "-p"
    # exec subcommand: prompt is also positional
    if profile.uses_exec_subcommand:
        profile.prompt_is_positional = True
        profile.prompt_flag = ""
    # Claude uses subprocess cwd, not a --cd flag
    if "claude" in profile.name.lower():
        profile.work_dir_flag = ""
    # If -p is a prompt arg (not print mode), --output-format
    # is likely tied to --print mode and will error in -p mode
    if not profile.prompt_is_positional and profile.output_format_flag:
        profile.output_format_flag = ""


def _has(text: str, pattern: str) -> bool:
    """Check if pattern exists in text (case-insensitive)."""
    return bool(re.search(pattern, text, re.IGNORECASE))
