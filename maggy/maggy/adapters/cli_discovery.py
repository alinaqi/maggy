"""Auto-discover installed AI CLIs and their command-line flags.

Probes each CLI via --help, parses capabilities, and builds
command templates that PiAdapter uses to spawn prompts.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_HELP_TIMEOUT = 10


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
        cmd = [self.binary]
        if self.uses_exec_subcommand:
            cmd.append("exec")
        elif self.uses_run_subcommand:
            cmd += ["run", self.run_model]
        if self.prompt_is_positional:
            if self.prompt_flag:
                cmd.append(self.prompt_flag)
            cmd.append(prompt)
        elif self.prompt_flag:
            cmd += [self.prompt_flag, prompt]
        else:
            cmd.append(prompt)
        if self.work_dir_flag:
            cmd += [self.work_dir_flag, wd]
        if self.auto_approve_flag:
            cmd.append(self.auto_approve_flag)
        if self.afk_flag:
            cmd.append(self.afk_flag)
        if self.output_format_flag:
            cmd += [self.output_format_flag, "text"]
        if self.max_turns_flag and max_turns > 0:
            cmd += [self.max_turns_flag, str(max_turns)]
        return cmd


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
    profile.version = _get_version(binary)
    help_text = _get_help(binary, "")
    _extract_flags(profile, help_text)
    if profile.uses_exec_subcommand:
        exec_help = _get_help(binary, "exec")
        _refine_from_exec(profile, exec_help)
    if profile.uses_run_subcommand:
        run_help = _get_help(binary, "run")
        _refine_from_run(profile, run_help)
    _post_process(profile)
    return profile


def _extract_flags(profile: CliProfile, text: str) -> None:
    """Extract flags by matching known flag names in help."""
    # Print/prompt mode
    if _has(text, r"-p,\s*--print\b"):
        profile.prompt_flag = "--print"
    elif _has(text, r"(-p|--prompt)\b"):
        profile.prompt_flag = "-p"
    # Working directory
    if _has(text, r"--work-dir\b"):
        profile.work_dir_flag = "-w"
    elif _has(text, r"-C,\s*--cd\b"):
        profile.work_dir_flag = "-C"
    elif _has(text, r"--cwd\b"):
        profile.work_dir_flag = "--cwd"
    # Auto-approve / skip permissions
    if _has(text, r"--dangerously-skip-permissions\b"):
        profile.auto_approve_flag = "--dangerously-skip-permissions"
    elif _has(text, r"--dangerously-bypass-approvals"):
        profile.auto_approve_flag = "--dangerously-bypass-approvals-and-sandbox"
    elif _has(text, r"--yolo\b"):
        profile.auto_approve_flag = "--yolo"
    elif _has(text, r"--auto-approve\b"):
        profile.auto_approve_flag = "--auto-approve"
    # Output format
    if _has(text, r"--output-format\b"):
        profile.output_format_flag = "--output-format"
    # Max turns / steps
    if _has(text, r"--max-turns\b"):
        profile.max_turns_flag = "--max-turns"
    elif _has(text, r"--max-steps-per"):
        profile.max_turns_flag = "--max-steps-per-turn"
    elif _has(text, r"--max-steps\b"):
        profile.max_turns_flag = "--max-steps"
    # AFK mode
    if _has(text, r"--afk\b"):
        profile.afk_flag = "--afk"
    # Exec subcommand for non-interactive use
    if _has(text, r"\bexec\b.*non-interactive"):
        profile.uses_exec_subcommand = True
    # Run subcommand (ollama-style: "run  Run a model")
    if _has(text, r"\brun\s+Run a model\b"):
        profile.uses_run_subcommand = True


def _refine_from_exec(profile: CliProfile, text: str) -> None:
    """Override flags with more specific exec subcommand flags."""
    if _has(text, r"-C,\s*--cd\b"):
        profile.work_dir_flag = "-C"
    if _has(text, r"--dangerously-bypass-approvals"):
        profile.auto_approve_flag = "--dangerously-bypass-approvals-and-sandbox"


def _refine_from_run(profile: CliProfile, text: str) -> None:
    """Extract flags from run subcommand help (ollama-style)."""
    profile.prompt_is_positional = True
    profile.prompt_flag = ""


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
    # run subcommand (ollama): prompt is positional, need model
    if profile.uses_run_subcommand:
        profile.prompt_is_positional = True
        profile.prompt_flag = ""
        if not profile.run_model:
            profile.run_model = _detect_ollama_model(profile)
    # Claude uses subprocess cwd, not a --cd flag
    if "claude" in profile.name.lower():
        profile.work_dir_flag = ""
    # If -p is a prompt arg (not print mode), --output-format
    # is likely tied to --print mode and will error in -p mode
    if not profile.prompt_is_positional and profile.output_format_flag:
        profile.output_format_flag = ""


def _detect_ollama_model(profile: CliProfile) -> str:
    """Find best coding model available in ollama."""
    try:
        out = subprocess.run(
            [profile.binary, "list"],
            capture_output=True, text=True,
            timeout=_HELP_TIMEOUT,
        )
        text = out.stdout.lower()
    except (subprocess.TimeoutExpired, OSError):
        return "qwen2.5-coder:32b"
    # Prefer coding models, then general, by size
    prefs = [
        "qwen2.5-coder:32b", "qwen2.5-coder:14b",
        "qwen2.5-coder:7b", "deepseek-coder-v2",
        "codellama:34b", "codellama:13b",
        "qwen3:32b", "llama3.1:70b", "llama3.1:8b",
    ]
    for model in prefs:
        if model.split(":")[0] in text:
            return model
    # Fallback: first listed model
    lines = out.stdout.strip().splitlines()
    if len(lines) > 1:
        return lines[1].split()[0]
    return "qwen2.5-coder:32b"


def _has(text: str, pattern: str) -> bool:
    """Check if pattern exists in text (case-insensitive)."""
    return bool(re.search(pattern, text, re.IGNORECASE))


def _get_version(binary: str) -> str:
    """Get CLI version string."""
    for flag in ("--version", "-V", "-v"):
        try:
            out = subprocess.run(
                [binary, flag],
                capture_output=True, text=True,
                timeout=_HELP_TIMEOUT, env=_clean_env(),
            )
            text = (out.stdout + out.stderr).strip()
            if text and len(text) < 200:
                return text.split("\n")[0]
        except (subprocess.TimeoutExpired, OSError):
            continue
    return ""


def _get_help(binary: str, subcommand: str) -> str:
    """Run --help and return output."""
    cmd = [binary]
    if subcommand:
        cmd.append(subcommand)
    cmd.append("--help")
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=_HELP_TIMEOUT, env=_clean_env(),
        )
        return (out.stdout + out.stderr).strip()
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Help failed for %s: %s", binary, exc)
        return ""


def _clean_env() -> dict[str, str]:
    """Return env without CLAUDECODE to avoid nesting block."""
    import os
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    return env
