# Behavioral Evals

Behavioral evals test whether skills produce the expected coding patterns when loaded into Claude Code. Each eval is a realistic coding task with a rubric.

## Structure

```
evals/
├── run-evals.sh              # Runner script
├── README.md                 # This file
├── {skill-name}/
│   └── scenario-N/
│       ├── task.md            # Coding task description
│       └── criteria.json      # Weighted rubric
```

## Scenario Format

### task.md

A realistic coding task that the skill should influence. Write it as you would a ticket or user request.

### criteria.json

```json
{
  "criteria": [
    {
      "name": "Short description",
      "type": "deterministic",
      "weight": 1.0,
      "check": "grep -q 'pattern' output.py"
    },
    {
      "name": "Code quality description",
      "type": "llm_judged",
      "weight": 0.5,
      "prompt": "Does the output follow X pattern? Answer yes/no with explanation."
    }
  ]
}
```

**Types:**
- `deterministic`: grep/regex/AST checks that can be automated
- `llm_judged`: requires LLM evaluation of output quality

## Running Evals

```bash
# All evals
./run-evals.sh

# Single skill
./run-evals.sh base

# With baseline comparison (with vs without skill)
./run-evals.sh --baseline base
```

## Adding New Evals

1. Create `evals/{skill-name}/scenario-N/`
2. Write `task.md` with a realistic coding task
3. Write `criteria.json` with weighted rubric
4. Test: `./run-evals.sh {skill-name}`

## Coverage

| Skill | Scenarios | Focus |
|-------|-----------|-------|
| base | 2 | Function length, TDD order |
| security | 2 | No hardcoded secrets, proper hashing |
| python | 1 | Type hints, pytest, ruff |
| typescript | 1 | Strict mode, barrel exports |
| react-web | 1 | Component structure, Zustand |
| session-management | 1 | Checkpoint creation |
| code-review | 1 | Review process |
| commit-hygiene | 1 | Atomic commits |
| agent-teams | 1 | Pipeline ordering |
| database-schema | 1 | Schema read before query |
| llm-patterns | 1 | Structured output, retry |
| supabase | 1 | RLS, migrations |
| credentials | 1 | Access.txt, .env.example |
| project-tooling | 1 | CLI verification |
| existing-repo | 1 | Repo analysis before changes |
