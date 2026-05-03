# Sync Agents

Sync project configuration between Claude Code, Kimi CLI, and Codex CLI.

Run this after `/initialize-project` or anytime you want to ensure all installed AI CLI tools have matching skills, project instructions, and hooks.

---

## Phase 1: Detect Installed Tools

```bash
BOOTSTRAP_DIR=$(cat ~/.claude/.bootstrap-dir 2>/dev/null)
if [ -z "$BOOTSTRAP_DIR" ]; then
    echo "Error: claude-bootstrap not installed. Run install.sh first."
    exit 1
fi
DETECTED=$("$BOOTSTRAP_DIR/scripts/detect-agents.sh" 2>/dev/null || echo "claude")
echo "Detected AI CLI tools: $DETECTED"
```

---

## Phase 2: Show Current State

Check what exists for each tool and present a status table:

```bash
echo "=== Current State ==="

# Claude
echo "Claude Code:"
[ -d ".claude/skills" ] && echo "  Skills:       .claude/skills/ ($(ls -d .claude/skills/*/ 2>/dev/null | wc -l | tr -d ' ') skills)" || echo "  Skills:       NOT SET UP"
[ -f "CLAUDE.md" ] && echo "  Instructions: CLAUDE.md" || echo "  Instructions: NOT SET UP"
[ -f ".claude/settings.json" ] && echo "  Hooks:        .claude/settings.json" || echo "  Hooks:        NOT SET UP"

# Kimi
echo "Kimi CLI:"
[ -d ".kimi/skills" ] && echo "  Skills:       .kimi/skills/ ($(ls -d .kimi/skills/*/ 2>/dev/null | wc -l | tr -d ' ') skills)" || echo "  Skills:       NOT SET UP"
echo "  Instructions: (Kimi uses skills directly, no project file needed)"
[ -f ".kimi/config.toml" ] && echo "  Hooks:        .kimi/config.toml" || echo "  Hooks:        NOT SET UP"

# Codex
echo "Codex CLI:"
[ -d ".codex/skills" ] && echo "  Skills:       .codex/skills/ ($(ls -d .codex/skills/*/ 2>/dev/null | wc -l | tr -d ' ') skills)" || echo "  Skills:       NOT SET UP"
[ -f "AGENTS.md" ] && echo "  Instructions: AGENTS.md" || echo "  Instructions: NOT SET UP"
[ -f ".codex/config.toml" ] && echo "  Hooks:        .codex/config.toml" || echo "  Hooks:        NOT SET UP"
```

Present the status table to the user, then ask what they want to do.

---

## Phase 3: Offer Sync Actions

Ask the user which actions to perform:

> **Current state shown above.** What would you like to sync?
>
> 1. **Sync all** - Copy skills + generate instructions + hooks for all detected tools
> 2. **Skills only** - Copy .claude/skills/ to .kimi/skills/ and .codex/skills/
> 3. **Generate AGENTS.md** - Create Codex project instructions from CLAUDE.md
> 4. **Generate config.toml** - Create Kimi/Codex hooks from settings.json
> 5. **Show diff** - Show what differs between tool configs

---

## Phase 4: Execute Sync

### Option 1: Sync All (or individual options below)

### Skills Sync
```bash
# Source of truth is .claude/skills/
if [ -d ".claude/skills" ]; then
    # Sync to Kimi
    if echo "$DETECTED" | grep -q "kimi"; then
        rm -rf .kimi/skills
        mkdir -p .kimi/skills
        cp -r .claude/skills/*/ .kimi/skills/ 2>/dev/null || true
        echo "Synced skills to .kimi/skills/"
    fi

    # Sync to Codex
    if echo "$DETECTED" | grep -q "codex"; then
        rm -rf .codex/skills
        mkdir -p .codex/skills
        cp -r .claude/skills/*/ .codex/skills/ 2>/dev/null || true
        echo "Synced skills to .codex/skills/"
    fi

    # Sync to generic .agents/ (works for any tool)
    rm -rf .agents/skills
    mkdir -p .agents/skills
    cp -r .claude/skills/*/ .agents/skills/ 2>/dev/null || true
    echo "Synced skills to .agents/skills/ (generic)"
else
    echo "No .claude/skills/ found. Run /initialize-project first."
fi
```

### Generate AGENTS.md (from CLAUDE.md)
If CLAUDE.md exists, generate AGENTS.md by:
1. Reading CLAUDE.md content
2. Replacing `.claude/skills/` paths with `.agents/skills/` paths
3. Writing as AGENTS.md

**Important:** AGENTS.md should reference `.agents/skills/` (generic path) since Codex reads from `.codex/skills/` and `.agents/skills/`. The `.agents/skills/` path is the cross-compatible choice.

If CLAUDE.md does not exist, copy from the bootstrap template:
```bash
cp "$BOOTSTRAP_DIR/templates/AGENTS.md" ./AGENTS.md
echo "Created AGENTS.md from template (customize for your project)"
```

### Generate config.toml
```bash
# For Kimi
if echo "$DETECTED" | grep -q "kimi"; then
    mkdir -p .kimi
    cp "$BOOTSTRAP_DIR/templates/config.toml" .kimi/config.toml
    echo "Created .kimi/config.toml with hooks"
fi

# For Codex
if echo "$DETECTED" | grep -q "codex"; then
    mkdir -p .codex
    cp "$BOOTSTRAP_DIR/templates/config.toml" .codex/config.toml
    echo "Created .codex/config.toml with hooks"
fi
```

---

## Phase 5: Summary

```
Sync complete!

Skills synced:
  .claude/skills/ -> .kimi/skills/  (N skills)
  .claude/skills/ -> .codex/skills/ (N skills)
  .claude/skills/ -> .agents/skills/ (N skills, generic)

Project instructions:
  CLAUDE.md   (Claude Code)
  AGENTS.md   (Codex CLI)

Hooks config:
  .claude/settings.json (Claude Code)
  .kimi/config.toml     (Kimi CLI)
  .codex/config.toml    (Codex CLI)

You can now run any of these in this project:
  claude    # Claude Code
  kimi      # Kimi CLI
  codex     # Codex CLI
```

---

## Phase 6: Update .gitignore

Ensure cross-tool directories are properly handled in .gitignore:

```bash
# Add to .gitignore if not present
for entry in ".kimi/" ".codex/" ".agents/"; do
    if ! grep -qF "$entry" .gitignore 2>/dev/null; then
        echo "$entry" >> .gitignore
    fi
done
```

**Note:** Unlike `.claude/` which is typically committed, `.kimi/` and `.codex/` project dirs should generally be gitignored since they're derived from `.claude/skills/`. The `/sync-agents` command regenerates them.

AGENTS.md **should** be committed (it's the Codex equivalent of CLAUDE.md).
