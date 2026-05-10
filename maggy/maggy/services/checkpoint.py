"""Cross-model checkpoint serializer.

Produces model-agnostic checkpoints that can be injected into
any model on switch, preserving task understanding.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class Checkpoint:
    """Model-agnostic task checkpoint."""

    goal: str = ""
    constraints: list[str] = field(default_factory=list)
    progress: list[str] = field(default_factory=list)
    working_state: str = ""
    file_context: list[str] = field(default_factory=list)
    source_model: str = ""
    created_at: str = ""

    def serialize(self) -> str:
        """Serialize to JSON for storage/transfer."""
        if not self.created_at:
            self.created_at = datetime.now(
                timezone.utc
            ).isoformat()
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def deserialize(cls, data: str) -> Checkpoint:
        """Reconstruct from JSON."""
        d = json.loads(data)
        return cls(**d)

    def to_prompt(self) -> str:
        """Format as a structured prompt for the new model."""
        parts = [
            "## Task Checkpoint (from previous model session)",
            f"**Goal:** {self.goal}",
        ]
        if self.constraints:
            parts.append("**Constraints:**")
            for c in self.constraints:
                parts.append(f"  - {c}")
        if self.progress:
            parts.append("**Progress so far:**")
            for p in self.progress:
                parts.append(f"  - {p}")
        if self.working_state:
            parts.append(
                f"**Current state:** {self.working_state}"
            )
        if self.file_context:
            parts.append("**Key files:**")
            for f in self.file_context[:10]:
                parts.append(f"  - {f}")
        parts.append(
            "\nPlease confirm you understand this context "
            "before proceeding."
        )
        return "\n".join(parts)


def create_checkpoint(
    goal: str,
    progress: list[str],
    model: str,
    working_state: str = "",
    files: list[str] | None = None,
    constraints: list[str] | None = None,
) -> Checkpoint:
    """Create a checkpoint from current session state."""
    return Checkpoint(
        goal=goal,
        constraints=constraints or [],
        progress=progress,
        working_state=working_state,
        file_context=files or [],
        source_model=model,
    )
