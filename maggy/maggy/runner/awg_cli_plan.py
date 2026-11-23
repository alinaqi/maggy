"""CliAwgClient's plan-graph calls: `awg create --parent`, `link`, `validation add`, `state`,
`decisions` and the REQUIREMENT nodes from the `show --json` context bundle."""

from __future__ import annotations

import json
from typing import cast

from maggy.runner.awg_cli_base import command, fence
from maggy.runner.awg_cli_graph import GraphCli
from maggy.runner.awg_errors import AwgError
from maggy.runner.awg_types import ChildSpec, Claim, EdgeSpec, ValidationSpec

REASON = "--reason=maggy plan stage"


class PlanCli(GraphCli):
    def create_child(self, claim: Claim, child: ChildSpec) -> dict:
        """create (fenced by the parent's lease) -> BACKLOG -> `task-plan` annotation. `awg
        create` makes the child READY, so a later failure cancels it before re-raising: the
        caller never learns its ref and could not roll it back."""
        options = [f"--parent={claim.ref}", *(f"--capability={c}" for c in child.capabilities),
                   *fence(claim)]
        made = cast(dict, self._agent(command("create", options, child.title)))
        ref = str(made["display_id"])
        try:
            self._shelve(ref, child.plan)
        except Exception:
            self._abandon(ref)
            raise
        return {**made, "state": "BACKLOG"}

    def _shelve(self, ref: str, plan: dict) -> None:
        self.set_state(ref, "BACKLOG")
        note = ["--kind=custom", "--title=task-plan", "--key=task-plan",
                f"--data={json.dumps(plan)}"]
        self._agent(command("annotate", note, ref))

    def _abandon(self, ref: str) -> None:
        """Best effort: the original failure is what the caller must see."""
        try:
            self.set_state(ref, "CANCELLED")
        except AwgError:
            pass

    def link(self, claim: Claim, edge: EdgeSpec) -> dict:
        options = [f"--lease={claim.ref}", *fence(claim)]
        argv = [*command("link", options, edge.source), edge.type, edge.target]
        return cast(dict, self._agent(argv))

    def add_validation(self, claim: Claim, spec: ValidationSpec) -> dict:
        """Unfenced: AWG fences `validation add` by the child's own lease, which nobody holds."""
        options = [f"--kind={spec.kind}", f"--title={spec.title}",
                   f"--min-trust={spec.min_trust}",
                   *([f"--requirement={spec.requirement}"] if spec.requirement else [])]
        return cast(dict, self._agent(["validation", *command("add", options, spec.work)]))

    def set_state(self, ref: str, state: str) -> dict:
        return cast(dict, self._agent([*command("state", [REASON], ref), state]))

    def decisions(self, ref: str) -> list[dict]:
        listed = cast(list, self._agent(command("decisions", [], ref)))
        return [{"id": d.get("id"), "key": (d.get("properties") or {}).get("key"),
                 "data": dict((d.get("properties") or {}).get("data") or {})} for d in listed]

    def requirements(self, ref: str) -> list[dict]:
        shown = cast(dict, self._agent(command("show", [], ref)))
        nodes = (shown.get("context") or {}).get("requirements") or []
        return [{"id": n.get("id"), "title": n.get("title", ""),
                 "criterion": (n.get("properties") or {}).get("id")} for n in nodes]
