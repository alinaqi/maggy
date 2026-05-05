---
name: polyphony
description: Multi-agent orchestration with container-isolated workspaces — each agent session runs in its own Docker container with independent git branches
when-to-use: Always loaded when container isolation is available (Docker/OrbStack installed). Default for /spawn-team.
user-invocable: false
effort: high
---

# Polyphony — Multi-Agent Orchestration

Container-isolated workspaces for parallel agent execution. Each agent gets its own Docker container with a full git clone on its own branch. No conflicts, independent tests, clean PRs.

---

## Architecture (6 Layers)

1. **Work Source** — Tasks from GitHub Issues (`gh api`) or local SQLite queue
2. **Orchestrator** — Supervisor loop: discover -> claim -> route -> provision -> run -> verify -> land
3. **Router** — Pure function: Task x Policy -> RunSpec (5-dimension complexity scoring)
4. **Identity Broker** — Resolves named credentials to volume mounts + env overlays
5. **Workspace Manager** — Per-task `git clone --reference`, branch checkout, cleanup
6. **Worker Runtime** — Docker container create/start/stop/logs lifecycle

---

## Task Lifecycle

```
DISCOVERED -> CLAIMED -> ROUTED -> PROVISIONED -> RUNNING -> VERIFYING -> LANDED
                                                     |           |
                                                     v           v
                                                   FAILED --> BLOCKED
                                                     |
                                                     v
                                                   CLAIMED (retry)
```

---

## Prerequisites

- Docker or OrbStack installed and running
- At least one agent CLI available (Claude, Codex, or Kimi)
- CLI subscriptions configured (not API keys)

Check:
```bash
command -v docker &>/dev/null || command -v orbctl &>/dev/null
```

---

## Configuration

All config lives in `~/.polyphony/`:

| File | Purpose |
|------|---------|
| `config.yaml` | Workspace root, poll interval, max concurrency |
| `identities.yaml` | Named credential bundles with volume paths |
| `agents.yaml` | Agent profiles (CLI commands, strengths) |
| `routing.yaml` | Routing rules and fallback chains |

Initialize with: `polyphony init`

---

## Routing Rules

Rules are evaluated top-down; first match wins. Each rule has a `match` predicate and an `agent` target.

```yaml
rules:
  - match: { task_type: docs, risk: low }
    agent: kimi
  - match: { task_type: bugfix }
    agent: codex
  - match: { risk: high }
    agent: claude
default:
  agent: claude
  fallback: [codex, kimi]
```

---

## Complexity Scoring (5 Dimensions)

Each dimension scores 0-2. Total 0-10.

| Dimension | Source |
|-----------|--------|
| Cyclomatic depth | LOC + scope size |
| Fan-out | Number of callers |
| Security boundary | Auth/PII keywords |
| Concurrency | Lock/transaction keywords |
| Domain invariants | Risk level + task type |

Routing thresholds:
- **0-3**: Delegate to Kimi solo
- **4-6**: Kimi + Codex review
- **7-10**: Claude direct

---

## Container Isolation

Each task gets:
- Its own Docker container from `polyphony-worker:latest`
- A full git clone at `/workspace` (not a worktree)
- Auth volumes mounted read-only (e.g., `~/.claude:/home/worker/.claude:ro`)
- Independent test execution
- Its own branch for PRs

---

## CLI Commands

```bash
polyphony init                    # Create ~/.polyphony/ with config templates
polyphony spawn "Fix auth bug"    # Create and route a task
polyphony status                  # Show task states
polyphony cleanup                 # Remove completed workspaces
```

---

## Integration with Existing Skills

- **cross-agent-delegation**: Uses Polyphony's complexity scoring for routing decisions
- **agent-teams**: Uses Polyphony's workspace isolation instead of shared directories
- **spawn-team**: Uses Polyphony's container provisioning for feature agents
