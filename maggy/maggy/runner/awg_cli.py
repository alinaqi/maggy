"""CliAwgClient: the AwgClient protocol over the awg CLI (`--token-file`, `--json`)."""

from __future__ import annotations

import json
from typing import cast

from maggy.runner.awg_cli_base import command, fence
from maggy.runner.awg_cli_plan import PlanCli
from maggy.runner.awg_errors import AwgError
from maggy.runner.awg_types import Claim, EvidenceSpec, claim_from_lease


class CliAwgClient(PlanCli):
    def next_claim(self, capabilities: list[str], require: list[str] | None = None) -> Claim | None:
        wanted = [f"--capabilities={','.join(capabilities)}",
                  *([f"--require-capabilities={','.join(require)}"] if require else [])]
        try:
            lease = self._agent(["next", "--claim", *wanted, "--json"])
        except AwgError as exc:
            if exc.code == "conflict":
                return None
            raise
        return claim_from_lease(cast(dict, lease))

    def heartbeat(self, claim: Claim) -> Claim:
        lease = cast(dict, self._agent(command("heartbeat", fence(claim), claim.ref)))
        expires = float(lease.get("lease_expires_at", claim.lease_expires))
        return claim.model_copy(update={"lease_expires": expires})

    def submit(self, claim: Claim, summary: str, sha: str) -> dict:
        options = [*fence(claim), f"--summary={summary}", f"--sha={sha}"]
        return cast(dict, self._agent(command("submit", options, claim.ref)))

    def release(self, claim: Claim, reason: str) -> dict:
        options = [*fence(claim), f"--reason={reason}"]
        return cast(dict, self._agent(command("release", options, claim.ref)))

    def block(self, claim: Claim, question: str, human: bool = True) -> dict:
        options = [*fence(claim), f"--reason={question}", *(["--human"] if human else [])]
        return cast(dict, self._agent(command("block", options, claim.ref)))

    def handoff(self, claim: Claim, text: str) -> dict:
        body = f"[handoff {claim.attempt_id}] {text}"
        return cast(dict, self._agent([*command("comment", [], claim.ref), body]))

    def annotate(self, claim: Claim, key: str, data: dict) -> dict:
        options = ["--kind=custom", f"--title={key}", f"--key={key}", f"--data={json.dumps(data)}"]
        return cast(dict, self._agent(command("annotate", options, claim.ref)))

    def annotations(self, ref: str) -> list[dict]:
        return cast(list, self._agent(command("annotations", [], ref)))

    def evidence(self, claim: Claim, spec: EvidenceSpec) -> dict:
        meta = [f"--meta={key}={value}" for key, value in sorted(spec.meta.items())]
        bound = [f"--validation={spec.validation}"] if spec.validation else []
        options = [f"--kind={spec.kind}", f"--verdict={spec.verdict}",
                   f"--commit-sha={spec.commit_sha}", *bound, *meta]
        return cast(dict, self._ci(command("evidence", options, claim.ref)))

    def show(self, ref: str) -> dict:
        """`awg show`, plus the validations from `awg proof` and the comment thread."""
        shown = cast(dict, self._agent(command("show", [], ref)))
        proof = cast(dict, self._agent(command("proof", [], ref)))
        comments = cast(dict, self._agent(command("comments", [], ref)))
        return {**shown, "validations": list(proof.get("validations") or []),
                "comments": list(comments.get("items") or [])}
