# Polyphony v0.1 — Multi-Agent Orchestration Specification

## Overview

Polyphony is a container-isolated multi-agent orchestration system for Maggy. Each agent session runs in its own Docker container with a full git clone on its own branch, enabling true parallel execution without conflicts.

## Architecture

Six layers, each with a single responsibility:

```
┌─────────────────────────────────────────┐
│  1. Work Source (GitHub Issues / Local)  │
├─────────────────────────────────────────┤
│  2. Orchestrator (Supervisor Loop)       │
├─────────────────────────────────────────┤
│  3. Router (Task x Policy -> RunSpec)    │
├─────────────────────────────────────────┤
│  4. Identity Broker (Credentials)        │
├─────────────────────────────────────────┤
│  5. Workspace Manager (Git Clones)       │
├─────────────────────────────────────────┤
│  6. Worker Runtime (Docker Containers)   │
└─────────────────────────────────────────┘
```

## §1 — Guiding Principles

- Container isolation per agent session
- Subscription-based auth (not API keys)
- Full git clones (not worktrees) for independence
- Pure function routing (deterministic, testable)
- State machine enforcement for task lifecycle
- Proof-of-work verification before landing

## §2 — Work Sources

Tasks enter the system from:

- **GitHub Issues**: Polled via `gh api`, filtered by label (default: `agent-ready`)
- **Local Queue**: SQLite-backed task queue at `~/.polyphony/queue.db`

Each source implements `poll() -> list[Task]` and `mark_claimed(task_id)`.

## §3 — Domain Models

### Task (§3.1)
Unit of work from a source. Fields: title, source, source_ref, state, task_type, scope, risk, context_tokens, requires_web, metadata.

### Identity (§3.2)
Named credential bundle. Fields: name, volumes (agent_type -> host_path), api_keys, cost_ceiling_usd_per_day.

### AgentProfile (§3.3)
Agent harness configuration. Fields: name, agent_type, cli_command, context_window_tokens, strengths, event_protocol, auth_path.

### RunSpec (§3.4)
Immutable execution specification for one attempt. Fields: task_id, agent, identity, workspace, image, attempt, model, fallback, max_turns, env_overlay, volume_mounts, deadline_seconds.

### Result (§3.5)
Outcome of a single run. Fields: task_id, run_spec_id, agent, status, turns, duration_seconds, cost_usd, artifacts, events.

## §4 — Task State Machine

```
DISCOVERED -> CLAIMED -> ROUTED -> PROVISIONED -> RUNNING -> VERIFYING -> LANDED
                                                     |           |
                                                     v           v
                                                   FAILED --> BLOCKED
                                                     |
                                                     v
                                                   CLAIMED (retry)
```

Terminal states: LANDED, BLOCKED.

Transitions are enforced by `can_transition(current, target)`. Invalid transitions raise `ValueError`.

## §5 — Routing

### §5.1 — Complexity Scoring

Five dimensions, each 0-2, total 0-10:

| Dimension | 0 | 1 | 2 |
|-----------|---|---|---|
| Cyclomatic depth | <10 LOC, 0-1 files | 10-50 LOC, 2-4 files | 50+ LOC, 5+ files |
| Fan-out | 0-2 callers | 3-10 callers | 11+ callers |
| Security boundary | No auth keywords | 1 keyword | 2+ keywords |
| Concurrency | No lock/transaction | 1 keyword | 2+ keywords |
| Domain invariants | Low risk, simple | Medium risk or refactor | High risk |

### §5.2-5.6 — Rule Evaluation

Rules are evaluated top-down. First match wins. Each rule has:
- `match`: Predicate fields (all must match)
- `agent`: Target agent name
- `fallback`: Ordered fallback chain

Default rule applies when no rules match.

## §6 — Workspace Manager

Each task+attempt gets:
- Directory at `{workspace_root}/{sanitized_task_id}/{attempt}/`
- Full `git clone` (with `--reference` and `--dissociate` if mirror available)
- Branch checkout to the specified ref
- Cleanup via `shutil.rmtree`

## §7 — Identity Broker

Resolves named identities to:
- **Volume mounts**: `{host_path}:/home/worker/{path}:ro` per agent type
- **Env overlays**: Environment variable pass-through from api_keys
- **Validation**: Name required, at least one volume required

## §8 — Worker Runtime

### Docker Lifecycle

```
docker create --name polyphony-{task_id}-{attempt} \
  -v {workspace}:/workspace \
  -v {auth_path}:/home/worker/{auth_path}:ro \
  -e {env_vars} \
  {image}

docker start {container_id}
docker wait {container_id}  # blocks until exit
docker logs {container_id}  # collect output
docker rm {container_id}    # cleanup
```

### §8.1 — Claude Adapter
Command: `claude -p --output-format stream-json`
Completion: `{"type": "result"}`
Quota: "rate limit" in output

### §8.2 — Codex Adapter
Command: `codex exec --full-auto`
Completion: `{"status": "completed"}`
Quota: "quota" in output

### §8.3 — Kimi Adapter
Command: `kimi --print -y`
Completion: `{"done": true}`
Quota: "rate limit" in output

## §9 — Event Protocol

Agent output is parsed as NDJSON (newline-delimited JSON). Each line is classified into a `TaskEvent` with kind (message, result, error, unknown) and data.

## §10 — Proof of Work

Before landing, the orchestrator verifies:
- Result status is "succeeded"
- Tests pass (if configured)
- Lint passes (if configured)
- Type check passes (if configured)

Failed verification transitions task to FAILED for retry or BLOCKED.

## §11 — Configuration

All configuration in `~/.polyphony/`:

- `config.yaml` — Global settings (workspace root, poll interval, concurrency)
- `identities.yaml` — Named credential bundles
- `agents.yaml` — Agent profiles and CLI commands
- `routing.yaml` — Routing rules and fallback chains

## §12 — Implementation

Core package: `scripts/polyphony/`

Modules: models, state_machine, store, config, scoring, router, identity, workspace, runtime, events, orchestrator, sources/*, adapters/*

CLI entry: `python3 -m polyphony {init|spawn|status|cleanup}`
