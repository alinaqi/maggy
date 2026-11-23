"""CliAwgClient's graph calls: `awg update`, `awg node create`, `awg decision`."""

from __future__ import annotations

import json
from typing import cast

from maggy.runner.awg_cli_base import CliBase, command
from maggy.runner.awg_types import Claim, NodeSpec, WorkUpdate


class GraphCli(CliBase):
    def update(self, claim: Claim, changes: WorkUpdate) -> dict:
        options = [*(f"--ac={line}" for line in changes.acceptance_criteria or []),
                   *(f"--capability={cap}" for cap in changes.capabilities or [])]
        return cast(dict, self._agent(command("update", options, claim.ref)))

    def create_node(self, claim: Claim, node: NodeSpec) -> dict:
        """`node create ... -- TITLE`: the title can never be read as an option."""
        options = [f"--type={node.type}", f"--parent={claim.ref}",
                   f"--data={json.dumps(node.data)}"]
        return cast(dict, self._agent(["node", *command("create", options, node.title)]))

    def decision(self, claim: Claim, key: str, data: dict) -> dict:
        options = [f"--key={key}", f"--data={json.dumps(data)}"]
        return cast(dict, self._agent(command("decision", options, claim.ref)))
