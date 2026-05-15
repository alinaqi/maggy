"""Tool call to MnemoNode extraction pipeline."""

from __future__ import annotations

from pathlib import Path

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import MnemoNode
from maggy.mnemos.scope import infer_scope_tags
from maggy.mnemos.signals import ToolSignal

TOOL_TO_NODE_TYPE: dict[str, str] = {
    "Read": "ContextNode",
    "Grep": "ContextNode",
    "Glob": "ContextNode",
    "Write": "ResultNode",
    "Edit": "ResultNode",
    "Bash": "ResultNode",
    "WebFetch": "ContextNode",
}


def classify_signal(signal: ToolSignal) -> str | None:
    """Map a tool signal to a node type."""
    return TOOL_TO_NODE_TYPE.get(signal.tool_name)


def extract_node_from_signal(
    signal: ToolSignal, task_id: str,
) -> MnemoNode | None:
    """Create a MnemoNode from a tool signal."""
    node_type = classify_signal(signal)
    if node_type is None:
        return None
    tags = infer_scope_tags(signal.file_path)
    return MnemoNode(
        type=node_type,
        task_id=task_id,
        content=_summarize_signal(signal),
        scope_tags=tags,
        origin="TOOL_RESULT",
    )


def detect_working_sequences(
    signals: list[ToolSignal],
) -> list[list[ToolSignal]]:
    """Group consecutive signals into working units."""
    if not signals:
        return []
    sequences: list[list[ToolSignal]] = []
    current: list[ToolSignal] = [signals[0]]
    for sig in signals[1:]:
        if _is_same_sequence(current[-1], sig):
            current.append(sig)
        else:
            if len(current) >= 2:
                sequences.append(current)
            current = [sig]
    if len(current) >= 2:
        sequences.append(current)
    return sequences


def extract_working_node(
    sequence: list[ToolSignal], task_id: str,
) -> MnemoNode:
    """Create a WorkingNode from a signal sequence."""
    tools = " -> ".join(s.tool_name for s in sequence)
    content = f"Sequence: {tools}"
    return MnemoNode(
        type="WorkingNode",
        task_id=task_id,
        content=content,
        origin="TOOL_RESULT",
    )


def run_extraction(
    signals: list[ToolSignal], task_id: str, db: MnemosDB,
) -> list[MnemoNode]:
    """Full extraction pipeline. Returns created nodes."""
    created: list[MnemoNode] = []
    seen_paths: set[str] = set()
    for sig in signals:
        node = extract_node_from_signal(sig, task_id)
        if node is None:
            continue
        # Deduplicate ContextNodes by file path
        if node.type == "ContextNode" and sig.file_path:
            if sig.file_path in seen_paths:
                continue
            seen_paths.add(sig.file_path)
        db.insert_node(node)
        created.append(node)
    # Extract WorkingNode sequences
    for seq in detect_working_sequences(signals):
        wn = extract_working_node(seq, task_id)
        db.insert_node(wn)
        created.append(wn)
    return created


def _summarize_signal(signal: ToolSignal) -> str:
    parts = [signal.tool_name]
    if signal.file_path:
        parts.append(signal.file_path)
    parts.append(f"[{signal.outcome}]")
    return " ".join(parts)


def _is_same_sequence(a: ToolSignal, b: ToolSignal) -> bool:
    """Heuristic: same sequence if within same directory."""
    if not a.file_path or not b.file_path:
        return True  # non-file tools group together
    da = str(Path(a.file_path).parent)
    db = str(Path(b.file_path).parent)
    return da == db
