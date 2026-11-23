"""FakeAwg's plan-graph calls: BACKLOG children with a task plan, links, validations, state."""

from __future__ import annotations

from maggy.runner.awg_errors import AwgError
from maggy.runner.awg_fake_graph import FakeGraph
from maggy.runner.awg_types import ChildSpec, Claim, EdgeSpec, ValidationSpec


class FakePlanGraph(FakeGraph):
    def create_child(self, claim: Claim, child: ChildSpec) -> dict:
        self._live(claim)
        ref = self.add_item(child.title, capabilities=child.capabilities)
        item = self.items[ref]
        item.parent, item.state = claim.ref, "BACKLOG"
        item.annotations.append({"key": "task-plan", "data": dict(child.plan),
                                 "attempt_id": claim.attempt_id})
        return {"display_id": ref, "state": item.state}

    def link(self, claim: Claim, edge: EdgeSpec) -> dict:
        self._live(claim)
        if edge.type == "DEPENDS_ON" and self._reaches(edge.target, edge.source):
            raise AwgError("dependency_cycle", f"{edge.source} -> {edge.target} closes a cycle")
        self.edges.append((edge.source, edge.type, edge.target))
        return {"source": edge.source, "type": edge.type, "target": edge.target}

    def add_validation(self, claim: Claim, spec: ValidationSpec) -> dict:
        self._live(claim)
        record = {"id": f"V-{sum(len(i.validations) for i in self.items.values()) + 1}",
                  **spec.model_dump(exclude={"work"}), "status": "PENDING"}
        self._item(spec.work).validations.append(record)
        return dict(record)

    def set_state(self, ref: str, state: str) -> dict:
        item = self._item(ref)
        item.state, item.version = state, item.version + 1
        return {"display_id": ref, "state": state}

    def _reaches(self, start: str, goal: str) -> bool:
        """`start` already depends (transitively) on `goal`."""
        seen, todo = set(), [start]
        while todo:
            ref = todo.pop()
            if ref == goal:
                return True
            seen.add(ref)
            todo += [t for s, kind, t in self.edges if s == ref and kind == "DEPENDS_ON"
                     and t not in seen]
        return False
