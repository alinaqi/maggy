# /polyphony-spawn — Spawn Task

Create a new task in the Polyphony orchestrator and route it to an agent.

---

## Usage

```
/polyphony-spawn <title> [--type <task_type>] [--risk <risk>] [--source <source>]
```

## Steps

### 1. Parse Arguments

- `title`: Required task description
- `--type`: Task type (feature, bugfix, docs, refactor, etc.). Default: feature
- `--risk`: Risk level (low, medium, high). Default: low
- `--source`: Work source (local, github). Default: local

### 2. Create Task

```bash
PYTHONPATH=scripts python3 -m polyphony spawn "$TITLE" --type "$TYPE"
```

### 3. Route Task

The orchestrator will automatically:
1. Score task complexity (5-dimension scoring)
2. Match against routing rules
3. Select agent and fallback chain
4. Provision container with workspace
5. Start agent execution

### 4. Report

Print task ID and routing decision.
