---
description: ADR enforcement — read architectural decisions before reviewing or modifying code
globs: ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.py", "**/*.go", "**/*.rs"]
---

## ADR Enforcement — Read Before Review or Modify

Before reviewing code or making architectural changes, check for ADRs:

### Pre-Review Gate
1. Check `docs/adr/` for existing Architecture Decision Records
2. Check `_project_specs/` for linked specifications
3. Check PR description and recent commits for ticket/issue references
4. If ADRs exist, review code AGAINST those documented decisions

### Pre-Modify Gate
Before changing architecture, patterns, or dependencies:
1. Read relevant ADRs in `docs/adr/`
2. If no ADR exists for the area being changed, flag it
3. For non-trivial changes: draft an ADR before implementing

### ADR Compliance
| Finding | Severity |
|---------|----------|
| Code contradicts accepted ADR | Critical — must fix |
| Architectural decision without ADR | High — create ADR |
| Stale/outdated ADR | Medium — update ADR |
| Minor drift from ADR intent | Low — note in review |

### Exempt from ADR
- Typo/comment fixes
- Dependency patch/minor bumps
- Test-only changes
- Changelog/README updates

### If No `docs/adr/` Directory
The project hasn't adopted ADRs yet. Ask the user:
"This project has no docs/adr/ directory. Want me to set one up and reverse-engineer ADRs from git history?"

### ADR Template Location
`~/.claude/templates/adr.md`

### Reverse-Engineer Protocol
When ADRs are missing:
1. `git log --oneline -10 -- <changed_files>` for intent
2. Read module structure and imports for patterns
3. Draft ADR with `Status: proposed`
4. Present to user for confirmation
