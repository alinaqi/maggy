# Contributing to Maggy

Thanks for your interest in contributing! This project aims to make AI-assisted development more reliable and consistent.

## Philosophy

Before contributing, understand the core philosophy:

1. **Complexity is the enemy** - Every line of code is a liability
2. **Measurable constraints** - Prefer specific numbers (20 lines/fn) over vague guidance
3. **Security is non-negotiable** - All projects must pass security checks
4. **AI-first thinking** - LLMs for logic, code for plumbing
5. **Spec-driven** - Define before you build

## How to Contribute

### Adding a New Skill

1. Create a directory in `skills/` with a lowercase hyphenated name
2. Add `SKILL.md` with YAML frontmatter:
   ```markdown
   ---
   name: my-skill
   description: One-line description of what this skill does
   when-to-use: When to activate this skill
   user-invocable: true
   effort: medium
   ---
   # My Skill

   ## Core Principles
   ...
   ```
3. Include these sections:
   - Core principles with measurable constraints
   - Project structure (if applicable)
   - Patterns with code examples (>= 1 per 50 lines)
   - Anti-patterns list
4. Keep under 500 lines (ideal: under 300)
5. Run the linter before submitting:
   ```bash
   PYTHONPATH=scripts python3 -m skill_lint --skill my-skill skills/
   ```
6. Update `README.md` to include the new skill

### Quality Gates

All skills must pass the automated linter before merge:

```bash
# Lint all skills
PYTHONPATH=scripts python3 -m skill_lint skills/

# Lint a single skill
PYTHONPATH=scripts python3 -m skill_lint --skill python skills/

# JSON output for CI
PYTHONPATH=scripts python3 -m skill_lint --format json skills/
```

**Checks enforced:**
- **FM001-FM009**: YAML frontmatter (name, description, format, fields)
- **SP001-SP003**: Spec compliance (SKILL.md exists, line count limits)
- **CQ001-CQ006**: Content quality (no ASCII art, no vague phrases, code examples)
- **RI001-RI002**: Cross-references (valid skill links, README listing)

Suppress known issues with inline comments:
```markdown
<!-- skill-lint: disable=SP002 -->
```

### Improving Existing Skills

1. Keep changes focused on one improvement
2. Maintain the existing structure
3. Ensure examples are correct and tested
4. Update version comments if significant

### Updating the Initialize Command

1. Test changes locally before submitting
2. Ensure idempotency - running twice shouldn't break anything
3. Preserve user customizations (never overwrite `_project_specs/`)

## Skill Guidelines

### Do

- Use specific, measurable constraints
- Provide working code examples
- Include anti-patterns with explanations
- Keep skills focused on one topic
- Reference other skills when building on them

### Don't

- Use vague guidance ("write clean code")
- Include time estimates
- Add features beyond what's needed
- Break existing projects when run as update

## Testing Your Changes

```bash
# Install your changes
./install.sh

# Test on a new project
mkdir test-project && cd test-project
claude
> /initialize-project

# Test on an existing project
cd existing-project
claude
> /initialize-project
# Should update skills without breaking existing config
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-skill`)
3. Make your changes
4. Test locally
5. Submit PR with clear description of changes

## Code of Conduct

- Be respectful and constructive
- Focus on technical merit
- Welcome newcomers
- Share knowledge freely

## Questions?

Open an issue for:
- Bug reports
- Feature requests
- Clarification on philosophy
- Help with implementation
