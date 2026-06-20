"""The agents: planner (blast radius + council sizing), reviewers, chair."""
from __future__ import annotations

from pydantic_ai import Agent

from .models import Refutation, ReviewPlan, Verdict
from .tools import register_tools

REFUTER_PROMPT = """You are a SKEPTICAL verifier. A reviewer flagged a BLOCKING finding. Try HARD
to DISPROVE it using your tools — grep the BARE symbol/string across the repo (NOT a line-spanning
pattern like `useEffect.*connect`; grep just `connect(` or the key name), and read the relevant file
region. Set refuted=true ONLY with concrete evidence the claim is false (cite the grep/read result).
If you cannot disprove it, set refuted=false — the finding stands.

Common false-positive classes — check these explicitly, because the diff a reviewer sees may be
TRUNCATED (huge PRs) and mislead them:
- "i18n / translation key missing" or "lacks German/de translation": OPEN the actual locale files
  and grep the bare key (its last segment). For this repo they live under
  libs/shared/services/translate/src/lib/locals/en/en.json and .../de/de.json. If the key (or its
  i18next plural variants key_one/key_other) exists in BOTH, the finding is FALSE — refuted=true.
- "new feature not feature-flagged" / "mounts unconditionally": a component being a NEW FILE does
  NOT mean the feature is new. grep where it's mounted (Router.tsx, route definitions) and check
  whether that ROUTE already exists on the base branch / is gated upstream. If the route/host
  predates this PR or the mount is already behind a flag, refuted=true.
- "symbol never called/defined": grep the bare symbol — if it IS referenced/defined, refuted=true.

A false 'blocking' on a PR is costly, so verify rigorously, but do not let a truncated diff trick
you into keeping a finding that the real files disprove."""

PLANNER_PROMPT = """You are the review CHAIR PLANNING how to review this PR. Use your tools
(list_changed_files, get_diff, read_file, grep, read_adr) to understand the change, then
produce a ReviewPlan:

- blast_radius: impacted_files (what else likely breaks/needs checking), impacted_symbols,
  impacted_endpoints, cross_service (does it cross a service/bounded-context boundary?),
  touches_auth_or_data (auth, migrations, money, or PII?), languages (subset of db/python/
  typescript actually changed), size (small=localized/low-risk, medium, large=wide or risky),
  and a one-line rationale.
- council_size: how many reviewer agents to summon, SIZED TO RISK — small=2, medium=3-4,
  large OR touches_auth_or_data OR cross_service=5(max).
- rounds: 1 normally; 2 (independent + discussion) for large or auth/data changes.
- chunks: ONLY for large PRs — split the changed files into coherent review areas (name,
  focus, files, languages); empty otherwise.

Be decisive and concrete. Use the tools before deciding."""

CHAIR_PROMPT = """You are the review CHAIR synthesizing the council. The individual reviewer
Verdicts are in the user message. Produce ONE final Verdict:
- decision: approve | changes_needed.
- summary: 2-4 sentences for the PR author.
- findings: a DEDUPED union of the reviewers' findings. KEEP file/line/severity so they post
  as inline comments. Before keeping a BLOCKING finding, sanity-check it with read_file/grep —
  DROP any blocking finding that lacks evidence or that you can disprove (e.g. a symbol the
  reviewer thought was undefined but read_file shows defined). A finding blocks only if THIS
  diff introduces it; pre-existing debt is a nit.
Approve only if no real blocking finding remains."""


def build_planner(model, with_tools: bool = True):
    a = Agent(model, output_type=ReviewPlan, retries=3, instructions=PLANNER_PROMPT)
    return register_tools(a) if with_tools else a


def build_reviewer(model, skill: str, focus: str = "", with_tools: bool = True):
    instr = skill + ("\n\n## This review\n" + focus if focus else "")
    a = Agent(model, output_type=Verdict, retries=3, instructions=instr)
    return register_tools(a) if with_tools else a


def build_chair(model, skill: str, with_tools: bool = True):
    a = Agent(model, output_type=Verdict, retries=3, instructions=skill + "\n\n" + CHAIR_PROMPT)
    return register_tools(a) if with_tools else a


def build_refuter(model):
    a = Agent(model, output_type=Refutation, retries=3, instructions=REFUTER_PROMPT)
    return register_tools(a)
