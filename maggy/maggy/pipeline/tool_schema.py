"""Typed tool definitions — allowlist-only, no shell passthrough."""

from __future__ import annotations

from dataclasses import dataclass, field

_VALID_RISKS = {"read", "write"}


@dataclass
class ParamDef:
    name: str
    param_type: str
    required: bool = True
    default: object = None


@dataclass
class ToolDef:
    name: str
    risk: str
    params: list[ParamDef] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.risk not in _VALID_RISKS:
            raise ValueError(f"Invalid risk: {self.risk}")


@dataclass
class ToolCall:
    name: str
    params: dict = field(default_factory=dict)


READ_TOOLS: dict[str, ToolDef] = {
    "file_read": ToolDef(
        "file_read", "read",
        [ParamDef("path", "str")],
    ),
    "grep": ToolDef(
        "grep", "read",
        [ParamDef("pattern", "str"), ParamDef("path", "str")],
    ),
    "git_status": ToolDef("git_status", "read"),
    "git_diff": ToolDef(
        "git_diff", "read",
        [ParamDef("ref", "str", required=False, default="HEAD")],
    ),
    "git_log": ToolDef(
        "git_log", "read",
        [ParamDef("n", "int", required=False, default=10)],
    ),
    "test_run": ToolDef(
        "test_run", "read",
        [ParamDef("timeout_s", "int", required=False, default=120)],
    ),
}

WRITE_TOOLS: dict[str, ToolDef] = {
    "file_write": ToolDef(
        "file_write", "write",
        [ParamDef("path", "str"), ParamDef("content", "str")],
    ),
    "file_edit": ToolDef(
        "file_edit", "write",
        [
            ParamDef("path", "str"),
            ParamDef("old", "str"),
            ParamDef("new", "str"),
        ],
    ),
    "git_commit": ToolDef(
        "git_commit", "write",
        [
            ParamDef("message", "str"),
            ParamDef("files", "list", required=False, default=None),
        ],
    ),
}

TOOL_ALLOWLIST: dict[str, ToolDef] = {**READ_TOOLS, **WRITE_TOOLS}


def validate_tool_call(call: ToolCall) -> bool:
    if call.name not in TOOL_ALLOWLIST:
        raise ValueError(f"Unknown tool: {call.name}")
    defn = TOOL_ALLOWLIST[call.name]
    for p in defn.params:
        if p.required and p.name not in call.params:
            raise ValueError(f"Missing required param: {p.name}")
    return True
