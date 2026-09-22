---
name: security-audit
description: Structured, adversarial, multi-phase security audit of a codebase — recon → coverage-led hunting → finder≠validator validation → machine-readable findings → target-neutral report
when-to-use: When asked to "security audit", "find vulnerabilities", "pen-test the code", or audit a codebase/PR for security before a release. For preventive coding patterns use `security`; for a quick branch review use `/security-review`.
user-invocable: true
allowed-tools: [Read, Glob, Grep, Bash, Task]
effort: high
---

# Security Audit — adversarial, evidence-grounded

A full audit, not a checklist. It runs in phases, keeps a coverage ledger so
nothing is skipped silently, and — the core discipline — **the agent that finds a
candidate is never the one that confirms it**. Severity is `likelihood × impact`,
not deviation from a style rule. Output is machine-readable and reproducible.

> Methodology inspired by Cloudflare's public security-audit-skill, rebuilt to
> reuse maggy's own pieces: `council-review` for adversarial validation,
> `cpg-analysis` (Joern/CodeQL) for static taint/data-flow, `agent-teams` /
> `polyphony` for isolated parallel hunters, and `security` for the vuln classes.

## Principles (read first)

- **Evidence over intuition.** A finding is `confirmed` only when you can name the
  file:line of the boundary that fails and a concrete attack that crosses it.
- **Finder ≠ validator.** Whoever proposes a candidate must not confirm it. A
  different agent (or a `council-review` model) tries to *disprove* it.
- **Impact-driven severity.** Rate `likelihood × impact`, not "differs from best
  practice". A hardcoded key in a test fixture is not critical; an auth bypass on
  a tenant boundary is.
- **Coverage is tracked, not assumed.** Every input surface / trust boundary is a
  ledger unit with a status; a coverage critic hunts the gaps.
- **No theater.** Do not pad the report with generic "consider using HTTPS"
  advice. Report only boundary failures you can stand behind.

## Phases

### 1. Reconnaissance → `architecture.md` + `coverage-ledger.json`
Map the target before hunting. Identify: entry points (HTTP routes, CLI, queue
consumers, webhooks), trust boundaries (authn/authz, tenant isolation, privilege
transitions), input surfaces (params, headers, files, env, deserialization),
secret handling, external calls (SSRF surface), and data stores. Write a short
`architecture.md`, then enumerate every surface as a unit in
`coverage-ledger.json` (`{id, surface, boundary, status: pending}`).

### 2. Coverage-led hunting
For each ledger unit, hunt the relevant classes. Prefer **isolated sub-agents**
(via `agent-teams` / `polyphony`) so one hunter's context does not bias another,
and lean on `cpg-analysis` for data-flow/taint where a graph beats grep. Mark each
unit `hunted`; a **coverage critic** pass re-reads the ledger and reopens units
that were skimmed. Classes to cover (depth in `security` + `cpg-analysis`):

| Class | Look for |
|-------|----------|
| Injection | SQL/NoSQL/OS/LDAP/template; unparameterized queries, `shell=True`, eval |
| AuthN / AuthZ | missing checks, IDOR, broken tenant isolation, JWT/session flaws |
| Secrets | keys in code/history/logs, client-exposed `VITE_/NEXT_PUBLIC_` secrets |
| SSRF / egress | user-controlled URLs, metadata endpoints, unvalidated redirects |
| Deserialization | pickle/yaml.load/Marshal on untrusted input |
| Path / file | traversal, arbitrary write, zip-slip, unsafe temp files |
| LLM / prompt | prompt injection, tool-abuse, unbounded fan-out, data exfil via output |
| Supply chain | typosquats, unpinned deps, postinstall scripts, CI token scope |
| Cloud / IaC | over-broad IAM, public buckets, exposed admin, secrets in env |
| Client-side | XSS, DOM sinks, CSP gaps, sensitive data in `localStorage` |
| Resource / DoS | unbounded loops/allocations, regex catastrophic backtracking |
| Data isolation | cross-tenant reads, missing RLS, PII in logs/caches |
| Memory (native) | overflow, UAF, integer wrap (for C/C++/unsafe Rust targets) |

### 3. Adversarial validation (finder ≠ validator)
For each unique candidate, a *different* reviewer attempts to **disprove** it:
is the tainted input actually reachable? is there a guard upstream? is the sink
real? Route this through `council-review` (multiple models vote) for anything
rated high/critical. Assign a verdict: `confirmed`, `needs_validation`, or
`rejected`.

### 4. Structured output → `findings.json`
Emit `findings.json` conforming to `report-schema.json` (shipped in this skill).
Validate it before reporting:
```bash
python3 "$(cat ~/.claude/.bootstrap-dir)/skills/security-audit/validate_findings.py" findings.json
```
The validator enforces the rules that keep the audit honest: unique ids, valid
enums, and that every `confirmed` finding has a file:line location, an attack
scenario, and a `validated_by` that differs from `found_by`.

### 5. Record verification
A fresh agent re-opens each `confirmed` finding and checks the cited file:line
*still* supports the claim (code may have moved). A material mismatch drops it
back to `needs_validation`.

### 6. Target-neutral report → `REPORT.md`
Write `REPORT.md` (executive summary + confirmed findings by severity),
`FINDINGS-DETAIL.md` (per-finding evidence + remediation), and
`NEEDS-VALIDATION.md` (candidates that could not be confirmed). Neutral tone: no
vendor names, no editorializing, just boundary → attack → impact → fix.

## Anti-patterns

- Confirming a finding you found yourself without an independent disprove attempt.
- Severity inflation ("uses md5" rated critical with no reachable attack).
- Grep-only hunting on a data-flow bug — use `cpg-analysis`.
- A report that lists advice instead of reachable, evidence-backed findings.
- Running audited target code outside a sandbox. Read and analyze; never execute
  untrusted target code to "see what it does".

## How it fits the harness

- Slots into the `base` Definition of Done for security-critical changes as the
  "prove it's safe" gate, above the preventive `security` skill.
- Reuses `council-review` (adversarial validation), `cpg-analysis` (static taint),
  `agent-teams` / `polyphony` (isolated parallel hunters).
- Iterations are additive: a second run over the same ledger typically surfaces
  more, so re-run before a major release rather than trusting one pass.
