---
name: council-review
description: Multi-model validation council — auto-validate plans, architecture changes, and PRs via validate-plan/review before executing
when-to-use: When you write a plan to ~/.claude/plans/, make architectural changes, or before marking a PR done; required for CLAUDE-tier tasks
user-invocable: false
allowed-tools: [Bash, Read]
effort: high
---

# Council of Experts — Multi-Model Validation

## When to Auto-Trigger

### Plans (auto_validate_plans)
When you write a plan to `~/.claude/plans/`, automatically validate it:
```bash
~/bin/validate-plan --threshold 2 ~/.claude/plans/<plan-file>.md
```
- 2+ of 3 approve → execute immediately
- 1 of 3 → surface reviewer feedback to user before proceeding
- 0 of 3 → revise plan, re-validate

### Architecture Decisions (auto_review_architecture)
When making architectural changes (new services, API redesigns, database schema changes), run:
```bash
~/bin/review --all "Review this architecture: <summary>"
```

### PR Review (auto_review_prs)
Before marking a PR as done, run:
```bash
~/bin/review --all --file <changed-files>
```

## Configuration

Council behavior is configured in `~/.claude/council.yaml`. The Maggy dashboard (Settings > Council) also manages this config.

### Chief of the Council

`chief: claude-fable-5` — Claude Fable 5 (Anthropic's most capable widely-released
model, GA 2026-06-09) leads every panel as the chief: it reviews first and casts
the deciding synthesis. Invoked via `~/bin/claude-fable-5`. Override the chief in
`~/.claude/council.yaml`.

### Reviewer Contexts

The chief leads each context, followed by the panel:

| Context | Default Reviewers | When |
|---------|-------------------|------|
| `plan` | **Claude Fable 5 (chief)**, DeepSeek Pro, Codex, Gemini Pro | Before executing any plan |
| `review` | **Claude Fable 5 (chief)**, DeepSeek Pro, Kimi | Code review, PR review |
| `architecture` | **Claude Fable 5 (chief)**, DeepSeek Pro, Gemini Pro, Grok | System design, schema changes |

### Threshold Rules

The `threshold` setting controls how many approvals are needed:
- `threshold: 2` with 3 reviewers → need 2/3 to auto-execute
- Clamped to [1, reviewer_count] — can't be 0 or exceed available reviewers

## Model Inventory

All 13 tiers are listed in `~/.claude/council.yaml` under `models:`. Each has:
- `id` — unique identifier
- `cmd` — CLI command to invoke (null for Claude models, which are the host)
- `tier` — routing priority (0=cheapest, 12=most capable)
- `label` — human-readable name

Use `POST /api/models/health` to verify all models are responding.

## How This Skill is Used

This skill is loaded by Claude Code on session start. It provides the behavioral rules for when to invoke multi-model validation. The actual execution happens via `~/bin/validate-plan` and `~/bin/review` which are already installed.

**Do not skip council validation for CLAUDE-tier tasks.** The whole point is that architecture and security decisions get independent verification before execution.
