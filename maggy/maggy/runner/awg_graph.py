"""The graph half of the AwgClient protocol: item updates, nodes, decisions, plan graph (§2.4)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from maggy.runner.awg_types import (
    ChildSpec, Claim, EdgeSpec, NodeSpec, ValidationSpec, WorkUpdate,
)


@runtime_checkable
class AwgGraph(Protocol):
    def update(self, claim: Claim, changes: WorkUpdate) -> dict:
        """Replace criteria and/or capabilities; changed criteria bump the WORK version."""

    def create_node(self, claim: Claim, node: NodeSpec) -> dict:
        """Create a node (e.g. REQUIREMENT) under the claimed item."""

    def decision(self, claim: Claim, key: str, data: dict) -> dict:
        """Record a DECISION node `key` on the item with structured `data`."""

    def decisions(self, ref: str) -> list[dict]:
        """The item's current decisions as {id, key, data}, oldest first."""

    def requirements(self, ref: str) -> list[dict]:
        """The item's REQUIREMENT nodes as {id, title, criterion (id or None)}."""

    def create_child(self, claim: Claim, child: ChildSpec) -> dict:
        """A child WORK item under the claimed one, in BACKLOG, with its task plan."""

    def link(self, claim: Claim, edge: EdgeSpec) -> dict:
        """A typed edge fenced by the claim; a DEPENDS_ON cycle raises `dependency_cycle`."""

    def add_validation(self, claim: Claim, spec: ValidationSpec) -> dict:
        """A required validation on `spec.work`, linked from its REQUIREMENT node."""

    def set_state(self, ref: str, state: str) -> dict:
        """Move an (unclaimed) item: BACKLOG, READY or CANCELLED."""

    def set_capabilities(self, ref: str, capabilities: list[str]) -> dict:
        """Replace an (unclaimed) item's claimer capabilities, e.g. its stage tag."""
