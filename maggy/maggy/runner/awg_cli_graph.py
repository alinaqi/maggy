"""CliAwgClient's graph calls: `awg update`, `awg node create`, `awg decision`."""

from __future__ import annotations

import json
from typing import cast

from maggy.runner.awg_cli_base import CliBase, command, fence
from maggy.runner.awg_types import Claim, NodeSpec, WorkUpdate


class GraphCli(CliBase):
    def update(self, claim: Claim, changes: WorkUpdate) -> dict:
        options = [*(f"--ac={line}" for line in changes.acceptance_criteria or []),
                   *(f"--capability={cap}" for cap in changes.capabilities or [])]
        return cast(dict, self._agent(command("update", options, claim.ref)))

    def create_node(self, claim: Claim, node: NodeSpec) -> dict:
        """`node create --title=T`: the title can never be read as an option. AWG nodes made
        this way carry no properties, so the data rides in the description; fenced by the
        item's lease (`--parent-work`)."""
        options = [f"--type={node.type}", f"--title={node.title}",
                   f"--description={json.dumps(node.data)}", f"--parent-work={claim.ref}",
                   *fence(claim), "--json"]
        return cast(dict, self._agent(["node", "create", *options]))

    def decision(self, claim: Claim, key: str, data: dict) -> dict:
        options = [f"--title={key}", f"--key={key}", f"--data={json.dumps(data)}", *fence(claim)]
        return cast(dict, self._agent(command("decision", options, claim.ref)))
