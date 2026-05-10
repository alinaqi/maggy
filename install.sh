#!/bin/bash

# Maggy Installer

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

echo "Installing Maggy v4.0.0..."
echo ""

# Save bootstrap directory location for other scripts
echo "$SCRIPT_DIR" > "$HOME/.claude/.bootstrap-dir"

# Create directories
mkdir -p "$CLAUDE_DIR/commands"
mkdir -p "$CLAUDE_DIR/skills"
mkdir -p "$CLAUDE_DIR/hooks"
mkdir -p "$CLAUDE_DIR/rules"

# Copy all commands
cp "$SCRIPT_DIR/commands/"*.md "$CLAUDE_DIR/commands/"
echo "✓ Installed commands:"
ls -1 "$CLAUDE_DIR/commands/" | sed 's/^/  - \//' | sed 's/\.md$//'

# Copy skills (folder structure with SKILL.md)
echo ""
echo "Installing skills..."
rm -rf "$CLAUDE_DIR/skills"
mkdir -p "$CLAUDE_DIR/skills"
skill_count=0
for skill_dir in "$SCRIPT_DIR/skills"/*/; do
    if [ -d "$skill_dir" ] && [ -f "$skill_dir/SKILL.md" ]; then
        skill_name=$(basename "$skill_dir")
        cp -r "${skill_dir%/}" "$CLAUDE_DIR/skills/"
        skill_count=$((skill_count + 1))
    fi
done
echo "✓ Installed $skill_count skills (folder/SKILL.md structure)"

# Cross-tool skill installation (Kimi CLI, Codex CLI)
DETECTED_AGENTS=$("$SCRIPT_DIR/scripts/detect-agents.sh" 2>/dev/null || true)

if echo "$DETECTED_AGENTS" | grep -q "kimi"; then
    "$SCRIPT_DIR/scripts/install-skills.sh" "$HOME/.kimi/skills" "$SCRIPT_DIR/skills"
    echo "  Also installed skills to ~/.kimi/skills/ (Kimi CLI)"
fi

if echo "$DETECTED_AGENTS" | grep -q "codex"; then
    "$SCRIPT_DIR/scripts/install-skills.sh" "$HOME/.codex/skills" "$SCRIPT_DIR/skills"
    echo "  Also installed skills to ~/.codex/skills/ (Codex CLI)"
fi

# Copy conditional rules
echo ""
echo "Installing conditional rules..."
rm -rf "$CLAUDE_DIR/rules"
mkdir -p "$CLAUDE_DIR/rules"
rule_count=0
for rule_file in "$SCRIPT_DIR/rules/"*.md; do
    if [ -f "$rule_file" ]; then
        cp "$rule_file" "$CLAUDE_DIR/rules/"
        rule_count=$((rule_count + 1))
    fi
done
echo "✓ Installed $rule_count conditional rules (with paths: frontmatter)"
ls -1 "$CLAUDE_DIR/rules/" | sed 's/^/  - /' | sed 's/\.md$//'

# Copy hooks
cp "$SCRIPT_DIR/hooks/"* "$CLAUDE_DIR/hooks/" 2>/dev/null || true
chmod +x "$CLAUDE_DIR/hooks/"* 2>/dev/null || true
echo ""
echo "✓ Installed git hooks (templates)"

# Copy templates
echo ""
echo "Installing templates..."
mkdir -p "$CLAUDE_DIR/templates"
cp "$SCRIPT_DIR/templates/"* "$CLAUDE_DIR/templates/" 2>/dev/null || true
chmod +x "$CLAUDE_DIR/templates/tdd-loop-check.sh" 2>/dev/null || true
chmod +x "$CLAUDE_DIR/templates/pre-compact.sh" 2>/dev/null || true
chmod +x "$CLAUDE_DIR/templates/codex-auto-review.sh" 2>/dev/null || true
echo "✓ Installed templates (CLAUDE.md, AGENTS.md, CLAUDE.local.md, settings.json, config.toml)"

# Cross-tool config installation
if echo "$DETECTED_AGENTS" | grep -q "kimi"; then
    mkdir -p "$HOME/.kimi"
    cp "$SCRIPT_DIR/templates/config.toml" "$HOME/.kimi/config.toml.bootstrap" 2>/dev/null || true
    echo "  Kimi: hooks template at ~/.kimi/config.toml.bootstrap"
fi

if echo "$DETECTED_AGENTS" | grep -q "codex"; then
    mkdir -p "$HOME/.codex"
    cp "$SCRIPT_DIR/templates/AGENTS.md" "$HOME/.codex/templates/AGENTS.md" 2>/dev/null || {
        mkdir -p "$HOME/.codex/templates"
        cp "$SCRIPT_DIR/templates/AGENTS.md" "$HOME/.codex/templates/AGENTS.md"
    }
    echo "  Codex: AGENTS.md template at ~/.codex/templates/"
fi

# Copy hook installer script
cp "$SCRIPT_DIR/scripts/install-hooks.sh" "$CLAUDE_DIR/" 2>/dev/null || true
chmod +x "$CLAUDE_DIR/install-hooks.sh" 2>/dev/null || true

# Copy graph tools installer
cp "$SCRIPT_DIR/scripts/install-graph-tools.sh" "$CLAUDE_DIR/" 2>/dev/null || true
chmod +x "$CLAUDE_DIR/install-graph-tools.sh" 2>/dev/null || true

# Install Polyphony CLI shim
POLYPHONY_SRC="$SCRIPT_DIR/scripts/polyphony"
if [ -f "$POLYPHONY_SRC/__main__.py" ]; then
    INSTALL_DIR="$HOME/.local/bin"
    mkdir -p "$INSTALL_DIR"
    cat > "$INSTALL_DIR/polyphony" << SHIM
#!/bin/bash
exec python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR/scripts'); from polyphony.__main__ import main; sys.exit(main())" "\$@"
SHIM
    chmod +x "$INSTALL_DIR/polyphony"
    echo ""
    echo "✓ Installed polyphony CLI shim"

    # Create default config if missing
    if [ ! -d "$HOME/.polyphony" ]; then
        mkdir -p "$HOME/.polyphony"
        cp -n "$SCRIPT_DIR/templates/polyphony-config.yaml" "$HOME/.polyphony/config.yaml" 2>/dev/null || true
        cp -n "$SCRIPT_DIR/templates/polyphony-identities.yaml" "$HOME/.polyphony/identities.yaml" 2>/dev/null || true
        cp -n "$SCRIPT_DIR/templates/polyphony-agents.yaml" "$HOME/.polyphony/agents.yaml" 2>/dev/null || true
        cp -n "$SCRIPT_DIR/templates/polyphony-routing.yaml" "$HOME/.polyphony/routing.yaml" 2>/dev/null || true
        echo "✓ Created ~/.polyphony/ config"
    fi
fi

# Run validation
echo ""
echo "Running validation..."
if [ -f "$SCRIPT_DIR/tests/validate-structure.sh" ]; then
    if "$SCRIPT_DIR/tests/validate-structure.sh" --quick; then
        echo ""
    else
        echo ""
        echo "⚠ Validation found issues. Run full validation:"
        echo "  $SCRIPT_DIR/tests/validate-structure.sh --full"
    fi
fi

echo ""
echo "================================================================"
echo "  Installation complete! (v4.0.0)"
echo "================================================================"
echo ""
echo "What's new in v4.0.0:"
echo "  - Polyphony: container-isolated parallel agents (Docker/OrbStack)"
echo "  - /spawn-team now uses Polyphony by default (fallback to native)"
echo "  - polyphony CLI: init, spawn, status, cleanup"
echo "  - Cross-tool support: Claude Code + Kimi CLI + Codex CLI"
echo ""
echo "Usage:"
echo "  1. Open any project folder"
echo "  2. Run: claude (or kimi, or codex)"
echo "  3. Type: /initialize-project"
echo ""
echo "Commands installed:"
echo "  /initialize-project   - Full project setup (includes Polyphony)"
echo "  /spawn-team           - Spawn agent team (containers by default)"
echo "  /sync-agents          - Sync config between Claude/Kimi/Codex"
echo "  /check-contributors   - Team coordination"
echo "  /update-code-index    - Regenerate code index"
echo ""
echo "Polyphony CLI:"
echo "  polyphony init        - Create ~/.polyphony/ config"
echo "  polyphony spawn       - Create and route a task"
echo "  polyphony status      - Show task states"
echo "  polyphony cleanup     - Remove completed workspaces"
echo ""
echo "Container isolation (Polyphony):"
if echo "$DETECTED_AGENTS" | grep -q "docker"; then
    echo "  [OK] Docker    - container isolation available"
elif echo "$DETECTED_AGENTS" | grep -q "orbstack"; then
    echo "  [OK] OrbStack  - container isolation available"
else
    echo "  [--] Docker    - not found (brew install --cask docker)"
fi
if echo "$DETECTED_AGENTS" | grep -q "polyphony"; then
    echo "  [OK] Polyphony - CLI installed"
else
    echo "  [--] Polyphony - CLI shim not on PATH (add ~/.local/bin to PATH)"
fi
echo ""
echo "Cross-tool compatibility:"
if echo "$DETECTED_AGENTS" | grep -q "kimi"; then
    echo "  [OK] Kimi CLI  - skills + hooks installed"
else
    echo "  [--] Kimi CLI  - not found (curl -L code.kimi.com/install.sh | bash)"
fi
if echo "$DETECTED_AGENTS" | grep -q "codex"; then
    echo "  [OK] Codex CLI - skills + AGENTS.md installed"
else
    echo "  [--] Codex CLI - not found (npm i -g @openai/codex)"
fi
echo ""
echo "Git Hooks (per-project):"
echo "  cd your-project && ~/.claude/install-hooks.sh"
echo ""
echo "Code Graph Tools:"
echo "  ~/.claude/install-graph-tools.sh            - Install Tier 1 (default)"
echo "  ~/.claude/install-graph-tools.sh --joern     - Also install Tier 2 (CPG)"
echo "  ~/.claude/install-graph-tools.sh --codeql    - Also install Tier 3 (security)"
echo "  ~/.claude/install-graph-tools.sh --all       - Install all tiers"
echo ""
echo "Validation:"
echo "  $SCRIPT_DIR/tests/validate-structure.sh --full"
echo ""
