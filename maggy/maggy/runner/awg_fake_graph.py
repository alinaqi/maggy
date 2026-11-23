"""FakeAwg's graph calls: update (version bump), nodes and decisions kept in memory."""

from __future__ import annotations

from maggy.runner.awg_fake_state import FakeAwgState
from maggy.runner.awg_types import Claim, NodeSpec, WorkUpdate


class FakeGraph(FakeAwgState):
    def update(self, claim: Claim, changes: WorkUpdate) -> dict:
        item = self._live(claim)
        if changes.acceptance_criteria is not None:
            item.acceptance_criteria = list(changes.acceptance_criteria)
        if changes.capabilities is not None:
            item.capabilities = frozenset(changes.capabilities)
        item.version += 1
        if changes.acceptance_criteria is not None:
            self.criteria_versions.setdefault(item.ref, []).append(item.version)
        return {"display_id": item.ref, "version": item.version}

    def create_node(self, claim: Claim, node: NodeSpec) -> dict:
        self._live(claim)
        return self._add_node({"type": node.type, "title": node.title, "data": dict(node.data)},
                              claim.ref)

    def decision(self, claim: Claim, key: str, data: dict) -> dict:
        self._live(claim)
        return self._add_node({"type": "DECISION", "key": key, "data": dict(data)}, claim.ref)

    def _add_node(self, node: dict, parent: str) -> dict:
        record = {"id": f"N-{len(self.nodes) + 1}", **node, "parent": parent}
        self.nodes.append(record)
        return dict(record)

    def decisions(self, ref: str) -> list[dict]:
        """Current decisions: a later one with the same key supersedes the earlier."""
        mine = [n for n in self.nodes if n["type"] == "DECISION" and n["parent"] == ref]
        current = [n for i, n in enumerate(mine)
                   if not any(later.get("key") == n.get("key") for later in mine[i + 1:])]
        return [{"id": n["id"], "key": n.get("key"), "data": dict(n.get("data") or {})}
                for n in current]

    def requirements(self, ref: str) -> list[dict]:
        return [{"id": n["id"], "title": n["title"], "criterion": (n.get("data") or {}).get("id")}
                for n in self.nodes if n["type"] == "REQUIREMENT" and n["parent"] == ref]
