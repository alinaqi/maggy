# Maggy: Project Instructions

Project-generic engineering policy. Personal model routing and tool wrappers
(model tiers, deepseek / kimi / gemini / grok CLIs, personal wrapper scripts) are not
project policy: they ship as the `token-economy` harness preset
(`maggy/maggy/harness/presets/token-economy.md`, enabled with
`maggy harness init --preset token-economy`).

## General Preferences

- Concise responses preferred
- Use TypeScript over JavaScript when possible
- Prefer functional programming patterns
- Write tests for new functionality

## Code Style

- 2 spaces for indentation (JS/TS)
- 4 spaces for Python
- Single quotes for strings (JS/TS)
- No trailing commas
- Meaningful variable names

## Git Workflow

- Write clear, concise commit messages
- One logical change per commit
- Run tests before committing
- **Update `CHANGELOG.md` in the same commit** — every behaviour/config/docs/deps
  change ships a changelog entry (see `rules/changelog.md`). No commit without one.

## Tools & Frameworks

- Package manager: npm (Node.js), pip (Python)
- Testing: Jest/Vitest (JS), pytest (Python)
- Linting: ESLint (JS), ruff/black (Python)

---

# Engineering Policy

## TDD — Non-Negotiable

ALWAYS write tests before implementation. No exceptions.

1. Read the requirement
2. Write failing tests that describe the expected behaviour
3. Run tests — confirm they fail for the right reason
4. Write the minimum implementation to pass
5. Refactor, keep tests green
6. Never write a function, class, or API endpoint without a corresponding test

If asked to add a feature without tests, write the tests first then ask to proceed.
If a PR diff shows untested code paths, flag them before continuing.

## Quality Gates

| Constraint | Limit |
|------------|-------|
| Lines per function | 20 max |
| Parameters per function | 3 max |
| Nesting depth | 2 levels max |
| Lines per file | 200 max |
| Functions per file | 10 max |
| Test coverage | 80% minimum |

Before completing any file, check these limits and split or decompose when exceeded
(see `rules/quality-gates.md`).

## Changelog

Every commit that changes behaviour, config, docs or dependencies updates
`CHANGELOG.md` in the same commit (see `rules/changelog.md`).

## PR Workflow — Required Steps

Before any PR is considered done:
1. All tests pass locally
2. Run the code review and fix every issue it flags
3. Confirm test coverage includes the new code paths
4. Write a clear PR description: what, why, how
