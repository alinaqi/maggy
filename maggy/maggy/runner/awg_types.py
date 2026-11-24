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
    validation: str | None = None  # the AWG validation id this evidence answers
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


class WorkUpdate(BaseModel):
    """Fields `awg update` replaces on a work item; None leaves a field unchanged."""

    model_config = ConfigDict(frozen=True)

    acceptance_criteria: list[str] | None = None
    capabilities: list[str] | None = None


class NodeSpec(BaseModel):
    """A graph node created under a work item (REQUIREMENT, VALIDATION, ...)."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(pattern=r"^[A-Z_]+$")
    title: str = Field(min_length=1)
    data: dict = Field(default_factory=dict)


class ChildSpec(BaseModel):
    """A child WORK item the plan stage creates under the claimed item (BACKLOG first).

    `plan` (description, files, test plan) is kept on the child as its `task-plan`
    annotation, which the build stage puts in the worker prompt."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    plan: dict = Field(default_factory=dict)


class EdgeSpec(BaseModel):
    """A typed edge, e.g. `AWG-9 DEPENDS_ON AWG-8` (AWG-9 waits for AWG-8)."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    type: str = Field(pattern=r"^[A-Z_]+$")
    target: str = Field(min_length=1)


class ValidationSpec(BaseModel):
    """A required validation on `work`, proving the REQUIREMENT node `requirement`."""

    model_config = ConfigDict(frozen=True)

    work: str = Field(min_length=1)
    kind: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1)
    min_trust: int = Field(ge=0, le=4)
    requirement: str | None = None


def annotation_key(annotation: dict) -> str:
    """An annotation row's key: `awg annotations --json` names it `idempotency_key`."""
    return str(annotation.get("key") or annotation.get("idempotency_key") or "")


def annotation_data(annotations: list[dict], key: str) -> dict | None:
    """The data of the first annotation keyed `key`, or None when there is none."""
    found = [dict(a.get("data") or {}) for a in annotations if annotation_key(a) == key]
    return found[0] if found else None
