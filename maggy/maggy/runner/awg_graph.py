"""The graph half of the AwgClient protocol: item updates, nodes and decisions (RFC §2.4)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from maggy.runner.awg_types import Claim, NodeSpec, WorkUpdate


@runtime_checkable
class AwgGraph(Protocol):
    def update(self, claim: Claim, changes: WorkUpdate) -> dict:
        """Replace criteria and/or capabilities; changed criteria bump the WORK version."""

    def create_node(self, claim: Claim, node: NodeSpec) -> dict:
        """Create a node (e.g. REQUIREMENT) under the claimed item."""

    def decision(self, claim: Claim, key: str, data: dict) -> dict:
        """Record a DECISION node `key` on the item with structured `data`."""
