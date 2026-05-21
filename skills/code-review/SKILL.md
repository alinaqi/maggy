---
name: code-review
description: Mandatory code reviews via /code-review before commits and deploys
when-to-use: When user asks to review code, before commits, or when /code-review is invoked
user-invocable: true
allowed-tools: [Read, Glob, Grep, Bash]
effort: high
---

# Code Review Skill


**Purpose:** Enforce automated code reviews as a mandatory guardrail before every commit and deployment. Choose between Claude, OpenAI Codex, Google Gemini, or multiple engines for comprehensive analysis.

**Sub-skills:**
- [adr-gate.md](./adr-gate.md) — Pre-review ADR and spec enforcement

---

## Pre-Review: ADR Gate (Mandatory)

Before any review engine runs, the ADR gate executes automatically:

1. **Classify** — trivial changes (typos, deps, tests-only) skip the gate
2. **Discover** — scan `docs/adr/`, `_project_specs/`, iCPG ReasonNodes, git history for linked ADRs and specs
3. **Enforce** — if no ADRs found for non-trivial changes:
   - **Interactive** (default): draft ADR from git history, ask user to confirm
   - **Unattended** (CI): write as `Status: proposed`, proceed
   - **Strict**: block review until ADR exists
4. **Inject** — feed discovered ADRs + specs into the review prompt as architectural context

### ADR Compliance Review Dimension

Added to the standard 7 review categories:

| Category | What It Checks |
|----------|----------------|
| **ADR Compliance** | Change conforms to documented decisions, no undocumented architectural shifts |

| Finding | Severity |
|---------|----------|
| Change contradicts accepted ADR | Critical |
| Architectural decision not in any ADR | High |
| ADR exists but is outdated/stale | Medium |
| Minor drift from ADR intent | Low |

See [adr-gate.md](./adr-gate.md) for full protocol, reverse-engineering rules, and configuration.

---

## Review Engine Choice

When running `/code-review`, users can choose their preferred review engine:

```
┌─────────────────────────────────────────────────────────────────┐
│  CODE REVIEW - Choose Your Engine                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ○ Claude (default)                                             │
│    Built-in, no extra setup, full conversation context          │
│                                                                 │
│  ○ OpenAI Codex CLI                                             │
│    GPT-5.2-Codex specialized for code review, 88% detection     │
│    Requires: npm install -g @openai/codex                       │
│                                                                 │
│  ○ Google Gemini CLI                                            │
│    Gemini 2.5 Pro with 1M token context, free tier available    │
│    Requires: npm install -g @google/gemini-cli                  │
│                                                                 │
│  ○ Dual Engine (any two)                                        │
│    Run two engines, compare findings, catch more issues         │
│                                                                 │
│  ○ All Three (maximum coverage)                                 │
│    Run Claude + Codex + Gemini for critical/security code       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Engine Comparison

| Aspect | Claude | Codex | Gemini | Multi-Engine |
|--------|--------|-------|--------|--------------|
| **Setup** | None | npm + OpenAI API | npm + Google Account | All setups |
| **Speed** | Fast | Fast | Fast | 2-3x time |
| **Context** | Conversation | Fresh per review | 1M tokens | N/A |
| **Detection** | Good | 88% (best) | 63.8% SWE-Bench | Combined |
| **Free Tier** | N/A | Limited | 1,000/day | Varies |
| **Best for** | Quick reviews | High accuracy | Large codebases | Critical code |

### Set Default Engine

```toml
# ~/.claude/settings.toml or project CLAUDE.md
[code-review]
default_engine = "claude"  # Options: claude, codex, gemini, dual, all
```

### Usage Examples

```bash
# Use default engine
/code-review

# Explicitly choose engine
/code-review --engine claude
/code-review --engine codex
/code-review --engine gemini

# Dual engine (pick any two)
/code-review --engine claude,codex
/code-review --engine claude,gemini
/code-review --engine codex,gemini

# All three engines
/code-review --engine all

# Quick shortcuts
/code-review              # Uses default
/code-review --codex      # Use Codex
/code-review --gemini     # Use Gemini
/code-review --all        # All three engines
```

---

## Multi-Engine Output

When using multiple engines, findings are compared and deduplicated:

### Dual Engine Example

```
┌─────────────────────────────────────────────────────────────────┐
│  CODE REVIEW RESULTS - DUAL ENGINE (Claude + Codex)             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✅ AGREED (Found by both):                                     │
│  🔴 SQL injection in auth.ts:45                                 │
│  🟡 Missing error handling in api.ts:112                        │
│                                                                 │
│  🔷 CLAUDE ONLY:                                                │
│  🟠 Potential race condition in worker.ts:89                    │
│  🟢 Consider extracting helper function                         │
│                                                                 │
│  🔶 CODEX ONLY:                                                 │
│  🟠 Memory leak - unclosed stream in upload.ts:34               │
│  🟡 N+1 query pattern in orders.ts:156                          │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  SUMMARY                                                        │
│  Agreed: 2 | Claude only: 2 | Codex only: 2                     │
│  Critical: 1 | High: 2 | Medium: 2 | Low: 1                     │
│  Status: ❌ BLOCKED - Fix critical/high issues                  │
└─────────────────────────────────────────────────────────────────┘
```

### Triple Engine Example (All Three)

```
┌─────────────────────────────────────────────────────────────────┐
│  CODE REVIEW RESULTS - TRIPLE ENGINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✅ UNANIMOUS (All 3 found):                                    │
│  🔴 SQL injection in auth.ts:45                                 │
│                                                                 │
│  ✅ MAJORITY (2 of 3 found):                                    │
│  🟠 Memory leak - unclosed stream in upload.ts:34 (Codex+Gemini)│
│  🟡 Missing error handling in api.ts:112 (Claude+Codex)         │
│                                                                 │
│  🔷 CLAUDE ONLY:                                                │
│  🟠 Potential race condition in worker.ts:89                    │
│                                                                 │
│  🔶 CODEX ONLY:                                                 │
│  🟡 N+1 query pattern in orders.ts:156                          │
│                                                                 │
│  🟢 GEMINI ONLY:                                                │
│  🟡 Consider using batch API for better performance             │
│  🟢 Type could be more specific in types.ts:23                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  SUMMARY                                                        │
│  Unanimous: 1 | Majority: 2 | Single: 5                         │
│  Critical: 1 | High: 2 | Medium: 3 | Low: 2                     │
│  Status: ❌ BLOCKED - Fix critical/high issues                  │
└─────────────────────────────────────────────────────────────────┘
```

### When to Use Each Mode

| Mode | Use When |
|------|----------|
| **Single (Claude)** | Quick in-flow reviews, exploration |
| **Single (Codex)** | CI/CD automation, high accuracy needed |
| **Single (Gemini)** | Large codebases (100+ files), free tier |
| **Dual** | Important PRs, pre-merge reviews |
| **Triple (All)** | Security-critical code, payment systems, auth |

---

## Core Philosophy

```
┌─────────────────────────────────────────────────────────────────┐
│  CODE REVIEW IS NON-NEGOTIABLE                                  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Every commit must pass code review.                            │
│  Every PR must be reviewed before merge.                        │
│  Every deployment must include review sign-off.                 │
│                                                                 │
│  AI catches what humans miss. Humans catch what AI misses.      │
│  Together: fewer bugs, cleaner code, better security.           │
├─────────────────────────────────────────────────────────────────┤
│  INVOKE: /code-review                                           │
│  PLUGIN: code-review@claude-plugins-official                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## When to Run Code Review

### Mandatory Review Points

| Trigger | Action | Command |
|---------|--------|---------|
| **Before commit** | Review staged changes | `/code-review` |
| **Before PR** | Review all changes vs base | `/code-review` |
| **Before merge** | Final review of PR | `/code-review` |
| **Before deploy** | Review deployment diff | `/code-review` |

### Automatic Integration

**Run code review automatically before every commit:**

```
┌─────────────────────────────────────────────────────────────────┐
│  COMMIT WORKFLOW                                                │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  1. Write code                                                  │
│  2. Run tests (TDD - must pass)                                 │
│  3. Run /code-review  ← MANDATORY                               │
│  4. Address critical/high issues                                │
│  5. Commit                                                      │
│  6. Push                                                        │
│                                                                 │
│  Skip step 3? ❌ NO COMMIT ALLOWED                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Using the Code Review Plugin

### Basic Usage

```bash
# Review current changes
/code-review

# Review specific files
/code-review src/auth/*.ts

# Review a PR
/code-review --pr 123

# Review with specific focus
/code-review --focus security
/code-review --focus performance
/code-review --focus architecture
```

### Review Categories

The code review plugin analyzes:

| Category | What It Checks |
|----------|----------------|
| **Security** | Vulnerabilities, injection risks, auth issues, secrets |
| **Performance** | N+1 queries, memory leaks, inefficient algorithms |
| **Architecture** | Design patterns, SOLID principles, coupling |
| **Code Quality** | Readability, complexity, duplication |
| **Best Practices** | Language idioms, framework conventions |
| **Testing** | Coverage gaps, test quality, edge cases |
| **Documentation** | Missing docs, outdated comments |

### Severity Levels

| Level | Action Required | Can Commit? |
|-------|-----------------|-------------|
| 🔴 **Critical** | Must fix immediately | ❌ NO |
| 🟠 **High** | Should fix before commit | ❌ NO |
| 🟡 **Medium** | Fix soon, can commit | ✅ YES |
| 🟢 **Low** | Nice to have | ✅ YES |
| ℹ️ **Info** | Suggestions only | ✅ YES |

---

## Pre-Commit Hook Integration

### Install Pre-Commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "🔍 Running code review..."

# Run Claude code review on staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(ts|tsx|js|jsx|py|go|rs)$')

if [ -n "$STAGED_FILES" ]; then
    # Invoke code review (requires claude CLI)
    claude --print "/code-review $STAGED_FILES" > /tmp/code-review-result.txt 2>&1

    # Check for critical/high issues
    if grep -q "🔴\|Critical\|🟠\|High" /tmp/code-review-result.txt; then
        echo "❌ Code review found critical/high issues:"
        cat /tmp/code-review-result.txt
        echo ""
        echo "Fix these issues before committing."
        exit 1
    fi

    echo "✅ Code review passed"
fi

exit 0
```

### Make Hook Executable

```bash
chmod +x .git/hooks/pre-commit
```

---

## Codex CLI Setup (For Codex/Both Modes)

If you want to use Codex or Both modes, install the Codex CLI:

```bash
# Prerequisites: Node.js 22+
node --version  # Must be 22+

# Install Codex CLI
npm install -g @openai/codex

# Authenticate (choose one):
# Option 1: ChatGPT subscription (Plus, Pro, Team, Enterprise)
codex  # Follow prompts to sign in

# Option 2: API key
export OPENAI_API_KEY=sk-proj-...
```

### Verify Installation

```bash
# Check Codex is installed
codex --version

# Test review
codex
> /review
```

See `codex-review.md` skill for full Codex documentation.

---

## Gemini CLI Setup (For Gemini/Multi-Engine Modes)

If you want to use Gemini or multi-engine modes, install the Gemini CLI:

```bash
# Prerequisites: Node.js 20+
node --version  # Must be 20+

# Install Gemini CLI
npm install -g @google/gemini-cli

# Or via Homebrew (macOS)
brew install gemini-cli

# Install Code Review extension
gemini extensions install https://github.com/gemini-cli-extensions/code-review
```

### Authenticate

```bash
# Option 1: Google Account (recommended, 1000 req/day free)
gemini  # Follow browser login prompts

# Option 2: API key (100 req/day free)
export GEMINI_API_KEY="your-key-from-aistudio.google.com"
```

### Verify Installation

```bash
# Check Gemini is installed
gemini --version

# List extensions
gemini extensions list

# Test review
gemini
> /code-review
```

See `gemini-review.md` skill for full Gemini documentation.

---

## CI/CD Integration

### GitHub Actions - Claude Only

```yaml
# .github/workflows/code-review.yml
name: Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  code-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Get changed files
        id: changed-files
        run: |
          echo "files=$(git diff --name-only origin/${{ github.base_ref }}...HEAD | tr '\n' ' ')" >> $GITHUB_OUTPUT

      - name: Run Claude Code Review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          npx @anthropic-ai/claude-code --print "/code-review ${{ steps.changed-files.outputs.files }}" > review.md

      - name: Post Review Comment
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const review = fs.readFileSync('review.md', 'utf8');

            github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: `## 🔍 Claude Code Review\n\n${review}`
            });

      - name: Check for Critical Issues
        run: |
          if grep -q "Critical\|🔴" review.md; then
            echo "❌ Critical issues found"
            exit 1
          fi
```

### GitHub Actions - Codex Only

```yaml
# .github/workflows/codex-review.yml
name: Codex Code Review

on:
  pull_request:

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Codex Review
        uses: openai/codex-action@main
        with:
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          model: gpt-5.2-codex
          safety_strategy: drop-sudo
```

### GitHub Actions - Both Engines

```yaml
# .github/workflows/dual-review.yml
name: Dual Code Review

on:
  pull_request:

jobs:
  claude-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Claude Review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          npx @anthropic-ai/claude-code --print "/code-review" > claude-review.md

      - uses: actions/upload-artifact@v4
        with:
          name: claude-review
          path: claude-review.md

  codex-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-node@v4
        with:
          node-version: '22'

      - name: Install Codex
        run: npm install -g @openai/codex

      - name: Codex Review
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          codex exec --full-auto --sandbox read-only \
            --output-last-message codex-review.md \
            "Review this code for bugs, security issues, and quality problems"

      - uses: actions/upload-artifact@v4
        with:
          name: codex-review
          path: codex-review.md

  combine-reviews:
    needs: [claude-review, codex-review]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4

      - name: Combine Reviews
        run: |
          echo "## 🔍 Dual Code Review Results" > combined-review.md
          echo "" >> combined-review.md
          echo "### Claude Findings" >> combined-review.md
          cat claude-review/claude-review.md >> combined-review.md
          echo "" >> combined-review.md
          echo "### Codex Findings" >> combined-review.md
          cat codex-review/codex-review.md >> combined-review.md

      - name: Post Combined Review
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const review = fs.readFileSync('combined-review.md', 'utf8');
            github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: review
            });
```

### GitHub Actions - Gemini Only

```yaml
# .github/workflows/gemini-review.yml
name: Gemini Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install Gemini CLI
        run: npm install -g @google/gemini-cli

      - name: Run Review
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          # Get diff
          git diff origin/${{ github.base_ref }}...HEAD > diff.txt

          # Run Gemini review
          gemini -p "Review this pull request diff for bugs, security issues, and code quality problems. Be specific about file names and line numbers.

          $(cat diff.txt)" > review.md

      - name: Post Review Comment
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const review = fs.readFileSync('review.md', 'utf8');
            github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: `## 🤖 Gemini Code Review\n\n${review}`
            });

      - name: Check for Critical Issues
        run: |
          if grep -qi "critical\|security vulnerability\|injection" review.md; then
            echo "❌ Critical issues found"
            exit 1
          fi
```

### GitHub Actions - All Three Engines

```yaml
# .github/workflows/triple-review.yml
name: Triple Engine Code Review

on:
  pull_request:

jobs:
  claude-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Claude Review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          npx @anthropic-ai/claude-code --print "/code-review" > claude-review.md

      - uses: actions/upload-artifact@v4
        with:
          name: claude-review
          path: claude-review.md

  codex-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-node@v4
        with:
          node-version: '22'

      - name: Install Codex
        run: npm install -g @openai/codex

      - name: Codex Review
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          codex exec --full-auto --sandbox read-only \
            --output-last-message codex-review.md \
            "Review this code for bugs, security issues, and quality problems"

      - uses: actions/upload-artifact@v4
        with:
          name: codex-review
          path: codex-review.md

  gemini-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install Gemini CLI
        run: npm install -g @google/gemini-cli

      - name: Gemini Review
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          git diff origin/${{ github.base_ref }}...HEAD > diff.txt
          gemini -p "Review this code diff for bugs, security, and quality issues:
          $(cat diff.txt)" > gemini-review.md

      - uses: actions/upload-artifact@v4
        with:
          name: gemini-review
          path: gemini-review.md

  combine-reviews:
    needs: [claude-review, codex-review, gemini-review]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4

      - name: Combine Reviews
        run: |
          echo "## 🔍 Triple Engine Code Review Results" > combined-review.md
          echo "" >> combined-review.md
          echo "### 🟣 Claude Findings" >> combined-review.md
          cat claude-review/claude-review.md >> combined-review.md
          echo "" >> combined-review.md
          echo "---" >> combined-review.md
          echo "### 🟢 Codex Findings" >> combined-review.md
          cat codex-review/codex-review.md >> combined-review.md
          echo "" >> combined-review.md
          echo "---" >> combined-review.md
          echo "### 🔵 Gemini Findings" >> combined-review.md
          cat gemini-review/gemini-review.md >> combined-review.md

      - name: Post Combined Review
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const review = fs.readFileSync('combined-review.md', 'utf8');
            github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: review
            });

      - name: Check Critical Issues
        run: |
          # Fail if any engine found critical issues
          if grep -qi "critical\|🔴" combined-review.md; then
            echo "❌ Critical issues found by at least one engine"
            exit 1
          fi
```

---

## Review Checklist

### Before Every Commit

- [ ] Run `/code-review` on staged changes
- [ ] No critical (🔴) issues
- [ ] No high (🟠) issues
- [ ] Security concerns addressed
- [ ] Performance issues considered

### Before Every PR

- [ ] Full code review of all changes
- [ ] All critical/high issues resolved
- [ ] Tests added for new functionality
- [ ] Documentation updated if needed

### Before Every Deployment

- [ ] Final review of deployment diff
- [ ] Security scan passed
- [ ] No new vulnerabilities introduced
- [ ] Rollback plan documented

---

## Common Review Findings

### Security Issues (Always Fix)

| Issue | Example | Fix |
|-------|---------|-----|
| SQL Injection | `query = f"SELECT * FROM users WHERE id = {id}"` | Use parameterized queries |
| XSS | `innerHTML = userInput` | Sanitize or use textContent |
| Secrets in code | `apiKey = "sk-xxx"` | Use environment variables |
| Missing auth | Unprotected endpoints | Add authentication middleware |
| Insecure crypto | MD5/SHA1 for passwords | Use bcrypt/argon2 |

### Performance Issues (Should Fix)

| Issue | Example | Fix |
|-------|---------|-----|
| N+1 queries | Loop with individual queries | Use batch/eager loading |
| Memory leak | Unclosed connections | Use connection pooling |
| Missing index | Slow queries | Add database indexes |
| Large payload | Fetching unused fields | Select only needed fields |
| No pagination | Loading all records | Implement pagination |

### Code Quality (Nice to Fix)

| Issue | Example | Fix |
|-------|---------|-----|
| Long function | 100+ lines | Extract into smaller functions |
| Deep nesting | 5+ levels | Early returns, extract methods |
| Magic numbers | `if (status === 3)` | Use named constants |
| Duplicate code | Copy-pasted blocks | Extract shared function |
| Missing types | `any` everywhere | Add proper TypeScript types |

---

## Post-Review: Decision Extraction

After review completes, extract architectural decisions automatically:

1. If review flagged new architectural choices → prompt to create ADR in `docs/adr/`
2. If review approved a new pattern → log to `_project_specs/session/decisions.md`
3. If review found ADR drift → flag the ADR for update or supersede

```markdown
### Auto-Log Entry (decisions.md)
- [YYYY-MM-DD] **[Review Finding]**: Brief description
  - Source: Code review of [PR/commit]
  - ADR: Created/Updated ADR-NNNN
  - Impact: What changed
```

---

## Integration with TDD Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  TDD + CODE REVIEW WORKFLOW                                     │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  1. RED: Write failing tests                                    │
│  2. GREEN: Write code to pass tests                             │
│  3. REFACTOR: Clean up code                                     │
│  4. REVIEW: Run /code-review  ← NEW STEP                        │
│  5. FIX: Address critical/high issues                           │
│  6. VALIDATE: Lint + TypeCheck + Coverage                       │
│  7. COMMIT: Only after review passes                            │
│                                                                 │
│  Review catches what tests miss:                                │
│  - Security vulnerabilities                                     │
│  - Performance issues                                           │
│  - Architecture problems                                        │
│  - Code maintainability                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Review Response Template

When code review finds issues, respond with:

```markdown
## Code Review Results

### 🔴 Critical Issues (Must Fix)
1. **SQL Injection in userController.ts:45**
   - Issue: User input directly interpolated into query
   - Fix: Use parameterized query
   - Code: `db.query('SELECT * FROM users WHERE id = $1', [userId])`

### 🟠 High Issues (Should Fix)
1. **Missing authentication on /api/admin endpoints**
   - Issue: Admin routes accessible without auth
   - Fix: Add auth middleware

### 🟡 Medium Issues (Fix Soon)
1. **N+1 query in getOrders function**
   - Consider eager loading or batch query

### 🟢 Low Issues (Nice to Have)
1. **Consider extracting validation logic to separate file**

### ✅ Strengths
- Good test coverage
- Clear function names
- Proper error handling

### 📊 Summary
- Critical: 1 | High: 1 | Medium: 1 | Low: 1
- **Status: ❌ BLOCKED** - Fix critical/high issues before commit
```

---

## Claude Instructions

### When to Invoke Code Review

Claude should automatically suggest or run code review:

1. **After completing a feature** → "Let me run a code review before we commit"
2. **Before creating a PR** → "Running code review on all changes"
3. **When user says "commit"** → "First, let me review the changes"
4. **After fixing bugs** → "Reviewing the fix for any issues"

### Review Focus Areas

Prioritize review based on change type:

| Change Type | Focus Areas |
|-------------|-------------|
| Auth/Security code | Security, input validation, crypto |
| Database code | SQL injection, N+1, transactions |
| API endpoints | Auth, rate limiting, validation |
| Frontend code | XSS, state management, performance |
| Infrastructure | Secrets, permissions, logging |

---

## Quick Reference

### Commands

```bash
# Basic review
/code-review

# Review specific files
/code-review src/auth.ts src/users.ts

# Review with focus
/code-review --focus security

# Review PR
/code-review --pr 123
```

### Severity Actions

```
🔴 Critical → STOP. Fix now. No commit.
🟠 High     → STOP. Fix now. No commit.
🟡 Medium   → Note it. Fix soon. Can commit.
🟢 Low      → Optional. Nice to have.
ℹ️ Info     → FYI only.
```

### Workflow

```
Code → Test → Review → Fix → Commit → Push → PR → Review → Merge → Deploy
              ↑                              ↑                    ↑
           /code-review                /code-review          /code-review
```
