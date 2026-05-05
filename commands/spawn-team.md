# /spawn-team - Spawn Agent Team

Spawn the default agent team for this project. Creates a coordinated team of agents that implement features in parallel following the strict TDD pipeline.

**Pipeline:** Specs > Tests > Ensure tests fail > Implement > Test again > Code Review > Security > Create branch > Create PR

---

## Phase 1: Prerequisites Check

### 1.1 Detect Container Mode

Check if Polyphony container isolation is available. **Container mode is the default when both Docker and polyphony CLI are present.**

```bash
BOOTSTRAP_DIR=$(cat ~/.claude/.bootstrap-dir 2>/dev/null)
DETECTED_AGENTS=$("$BOOTSTRAP_DIR/scripts/detect-agents.sh" 2>/dev/null || echo "claude")

CONTAINER_MODE="false"
if echo "$DETECTED_AGENTS" | grep -qE "docker|orbstack"; then
    if command -v polyphony &>/dev/null; then
        CONTAINER_MODE="true"
        echo "✓ Container mode: ON (Docker + polyphony detected)"
        echo "  Each feature agent will run in its own isolated container"
    else
        echo "⚠ Docker found but polyphony CLI missing"
        echo "  Run: cd \$(cat ~/.claude/.bootstrap-dir) && ./install.sh"
        echo "  Falling back to native agents (shared workspace)"
    fi
else
    echo "ℹ Docker not found — using native agents (shared workspace)"
    echo "  Install Docker for container isolation: brew install --cask docker"
fi
```

### 1.2 Check Agent Definitions

Verify `.claude/agents/` exists and has the required agent definitions:

```bash
ls .claude/agents/
```

Required files (with proper frontmatter: name, description, model, tools, disallowedTools, maxTurns):
- `team-lead.md`
- `quality.md`
- `security.md`
- `code-review.md`
- `merger.md`
- `feature.md`

If missing, copy from the agent-teams skill:
```bash
cp -r ~/.claude/skills/agent-teams/agents/ .claude/agents/
```

### 1.3 Check Feature Specs

```bash
ls _project_specs/features/
```

If no feature specs exist, ask the user:

> **No feature specs found.** The agent team needs features to implement.
>
> What are the key features of this project? I'll create a spec file for each one.

For each feature the user lists, create `_project_specs/features/{feature-name}.md` with a skeleton spec.

### 1.4 Check GitHub CLI

```bash
gh auth status
```

Needed by the merger agent for PR creation. Warn if not authenticated but don't block.

### 1.5 Ensure Worker Image (container mode only)

```bash
if [ "$CONTAINER_MODE" = "true" ]; then
    if ! docker image inspect polyphony-worker:latest &>/dev/null 2>&1; then
        echo "Building polyphony-worker image..."
        docker build -t polyphony-worker:latest \
            -f "$BOOTSTRAP_DIR/templates/Dockerfile.polyphony" "$BOOTSTRAP_DIR"
        echo "✓ Built polyphony-worker:latest"
    else
        echo "✓ polyphony-worker:latest image ready"
    fi
fi
```

---

## Phase 2: Spawn Default Agents

Spawn the 5 permanent agents **natively** (these are coordination agents — they read/verify, not write code). Each agent reads `.claude/agents/{type}.md` for its full definition including frontmatter (tools, model, maxTurns, etc.).

> **Note:** Permanent agents always run natively regardless of container mode. Only feature agents get containers.

### 2.1 Team Lead
```
Agent tool:
  name: "team-lead"
  subagent_type: "team-lead"
  prompt: "You are the team lead. Read .claude/agents/team-lead.md for your full instructions. Start by reading _project_specs/features/*.md to identify features, then create task chains and spawn feature agents."
```

### 2.2 Quality Agent
```
Agent tool:
  name: "quality-agent"
  subagent_type: "quality-agent"
  prompt: "You are the quality agent. Read .claude/agents/quality.md for your instructions. Watch TaskList for tasks assigned to you. Process them in task ID order."
```

### 2.3 Security Agent
```
Agent tool:
  name: "security-agent"
  subagent_type: "security-agent"
  prompt: "You are the security agent. Read .claude/agents/security.md for your instructions. Watch TaskList for security-scan tasks assigned to you."
```

### 2.4 Code Review Agent
```
Agent tool:
  name: "review-agent"
  subagent_type: "review-agent"
  prompt: "You are the code review agent. Read .claude/agents/code-review.md for your instructions. Watch TaskList for code-review tasks assigned to you."
```

### 2.5 Merger Agent
```
Agent tool:
  name: "merger-agent"
  subagent_type: "merger-agent"
  prompt: "You are the merger agent. Read .claude/agents/merger.md for your instructions. Watch TaskList for branch-pr tasks assigned to you."
```

---

## Phase 3: Spawn Feature Agents

### Container Mode (default when Docker + polyphony available)

For each feature spec in `_project_specs/features/`:

```bash
# Polyphony creates a container with its own git clone + branch,
# then starts the agent CLI inside
polyphony spawn "{feature-name}: implement feature per _project_specs/features/{feature-name}.md" \
    --type feature --risk low
```

This does everything in one command:
1. Creates a task in Polyphony's store
2. Routes it to an agent via the routing policy
3. Provisions a Docker container with a full git clone
4. Creates a feature branch (`feature/{feature-name}`)
5. Starts the agent CLI inside the container

Check running containers:
```bash
polyphony status
```

### Fallback Mode (no Docker)

If container mode is not available, spawn feature agents natively (shared workspace):

```
Agent tool:
  name: "feature-{feature-name}"
  subagent_type: "feature-agent"
  prompt: "You are the feature agent for {feature-name}. Read .claude/agents/feature.md for your instructions. Your feature spec is at _project_specs/features/{feature-name}.md. Start by checking TaskList for your first task."
```

> **Advisory:** Running without container isolation (Docker not found). Agents share the workspace — coordinate carefully to avoid file conflicts.

---

## Phase 4: Team Status Summary

Show the user:

### Container Mode:
```
AGENT TEAM DEPLOYED (Container Isolation ON)
─────────────────────────────────────────────

Team: {project-name}
Features: {N}
Isolation: Polyphony containers (each feature has its own branch)

NATIVE AGENTS (coordination)
─────────────────────────────
  Team Lead        Orchestrating
  Quality Agent    Watching for verification tasks
  Security Agent   Watching for security scan tasks
  Code Review      Watching for review tasks
  Merger Agent     Watching for branch/PR tasks

CONTAINER AGENTS (isolated)
────────────────────────────
  feature-{name1}  Container running — branch: feature/{name1}
  feature-{name2}  Container running — branch: feature/{name2}

PIPELINE (per feature)
──────────────────────
Spec > Review > Tests > RED Verify > Implement >
GREEN Verify > Validate > Code Review > Security > Branch+PR

Monitor: polyphony status
Cleanup: polyphony cleanup (after all PRs created)
```

### Fallback Mode:
```
AGENT TEAM DEPLOYED (Shared Workspace)
───────────────────────────────────────

⚠ Docker not available — agents share the workspace

Team: {project-name}
Features: {N}
Total tasks: {N * 10}

AGENTS
──────
  Team Lead        Orchestrating
  Quality Agent    Watching for verification tasks
  Security Agent   Watching for security scan tasks
  Code Review      Watching for review tasks
  Merger Agent     Watching for branch/PR tasks
  feature-{name1}  Starting spec for {name1}
  feature-{name2}  Starting spec for {name2}

PIPELINE
────────
Spec > Review > Tests > RED Verify > Implement >
GREEN Verify > Validate > Code Review > Security > Branch+PR

The team runs autonomously until all PRs are created.
```

---

## Monitoring

After the team is spawned, the user can:
- **Check progress:** Ask team lead for status, or run `polyphony status` (container mode)
- **Message agents:** Use SendMessage to contact any agent
- **View container logs:** `docker logs polyphony-{feature-name}` (container mode)
- **Handle blockers:** Message the blocked agent or team lead

The team runs autonomously until all PRs are created, then the team lead shuts everything down.

### Cleanup (container mode)

After all PRs are created:
```bash
polyphony cleanup
```
This removes completed containers and workspaces. Branches and PRs are preserved on the remote.
