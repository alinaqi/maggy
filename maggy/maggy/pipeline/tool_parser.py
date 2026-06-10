"""Tool parser — extracts typed JSON tool calls from model output."""

from __future__ import annotations

import json
import re

from maggy.pipeline.tool_schema import TOOL_ALLOWLIST, ToolCall

_TOOL_BLOCK = re.compile(
    r"```tool_call\s*\n(.*?)\n```",
    re.DOTALL,
)


def parse_tool_calls(text: str) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for match in _TOOL_BLOCK.finditer(text):
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        name = data.get("name", "")
        if name not in TOOL_ALLOWLIST:
            continue
        params = data.get("params", {})
        calls.append(ToolCall(name=name, params=params))
    return calls


def extract_text_and_calls(
    text: str,
) -> dict:
    calls = parse_tool_calls(text)
    cleaned = _TOOL_BLOCK.sub("", text).strip()
    return {"text": cleaned, "calls": calls}
