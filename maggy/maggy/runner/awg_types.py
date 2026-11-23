"""Value types shared by the AwgClient implementations."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

TRUST = {"agent": 1, "reviewer": 2, "ci": 3, "human": 4, "owner": 4}


class Claim(BaseModel):
    """A live lease on one work item: every lifecycle call presents attempt + fencing token."""

    model_config = ConfigDict(frozen=True)

    ref: str
    work_id: str
    attempt_id: str
    fencing_token: int
    lease_expires: float
    version: int = 0
    title: str = ""
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    context: str = ""


class EvidenceSpec(BaseModel):
    """One commit-bound evidence record; attached with the ci credential only."""

    model_config = ConfigDict(frozen=True)

    kind: str = Field(min_length=1, max_length=40)
    verdict: str = Field(min_length=1)
    commit_sha: str = Field(min_length=1, max_length=80)
    meta: dict[str, str] = Field(default_factory=dict)


class AwgCliConfig(BaseModel):
    """Where awg lives and which token FILES it reads (secrets never enter argv)."""

    model_config = ConfigDict(frozen=True)

    binary: Path
    agent_token_file: Path
    ci_token_file: Path
    timeout_s: float = 60.0

    @model_validator(mode="after")
    def _separate_credentials(self) -> AwgCliConfig:
        if self.agent_token_file.resolve() == self.ci_token_file.resolve():
            raise ValueError("agent and ci credentials must be separate token files")
        return self


def claim_from_lease(lease: dict) -> Claim:
    """A Claim from `awg next --claim --json` output (lease plus context bundle)."""
    context = lease.get("context") or {}
    return Claim(ref=lease["display_id"], work_id=lease["work_id"],
                 attempt_id=lease["attempt_id"], fencing_token=int(lease["fencing_token"]),
                 lease_expires=float(lease["lease_expires_at"]),
                 version=int(lease.get("version", context.get("version", 0))),
                 title=context.get("goal", ""), description=context.get("description", ""),
                 acceptance_criteria=list(context.get("acceptance_criteria") or []),
                 context=json.dumps(context, indent=2, default=str))
