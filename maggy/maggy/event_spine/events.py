"""Eight typed event dataclasses for the Event Spine."""

from __future__ import annotations

from dataclasses import dataclass, field

from .header import EventHeader


@dataclass
class IntentEvent:
    """iCPG ReasonNode decomposition."""

    header: EventHeader = field(
        default_factory=lambda: EventHeader("intent")
    )
    intent_text: str = ""
    reason_node_id: str = ""
    decomposed_steps: list[str] = field(default_factory=list)


@dataclass
class BindingEvent:
    """Lexon tool selection + clarify mode."""

    header: EventHeader = field(
        default_factory=lambda: EventHeader("binding")
    )
    phrase: str = ""
    selected_tool: str = ""
    candidates: list[str] = field(default_factory=list)
    clarify_mode: str = ""  # self_clarify | user_clarify


@dataclass
class ExecutionEvent:
    """Tool invocation input/output/duration."""

    header: EventHeader = field(
        default_factory=lambda: EventHeader("execution")
    )
    tool_name: str = ""
    input_summary: str = ""
    output_summary: str = ""
    duration_ms: int = 0
    success: bool = True


@dataclass
class MemoryEvent:
    """Mnemos within-task memory write."""

    header: EventHeader = field(
        default_factory=lambda: EventHeader("memory")
    )
    memory_type: str = ""  # fact | decision | code_ref | handoff
    content: str = ""
    node_id: str = ""


@dataclass
class PersistenceEvent:
    """Engram cross-session promotion."""

    header: EventHeader = field(
        default_factory=lambda: EventHeader("persistence")
    )
    engram_id: str = ""
    memory_type: str = ""
    content: str = ""
    source_namespace: str = ""
    target_namespace: str = ""


@dataclass
class OutcomeEvent:
    """Process Intelligence success/failure + reward."""

    header: EventHeader = field(
        default_factory=lambda: EventHeader("outcome")
    )
    success: bool = True
    reward: float = 0.0
    metrics: dict = field(default_factory=dict)


@dataclass
class MutationEvent:
    """L2/L3/L4 self-modification."""

    header: EventHeader = field(
        default_factory=lambda: EventHeader("mutation")
    )
    control_level: str = ""  # L2 | L3 | L4
    target: str = ""
    old_value: str = ""
    new_value: str = ""
    reason: str = ""


@dataclass
class MeshEvent:
    """Cross-machine sharing + quarantine status."""

    header: EventHeader = field(
        default_factory=lambda: EventHeader("mesh")
    )
    peer_id: str = ""
    peer_name: str = ""
    action: str = ""  # share | receive | quarantine | promote
    memory_type: str = ""
    content_key: str = ""


EVENT_TYPES = {
    "intent": IntentEvent,
    "binding": BindingEvent,
    "execution": ExecutionEvent,
    "memory": MemoryEvent,
    "persistence": PersistenceEvent,
    "outcome": OutcomeEvent,
    "mutation": MutationEvent,
    "mesh": MeshEvent,
}
