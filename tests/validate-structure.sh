#!/bin/bash
# validate-structure.sh - Validates Maggy structure matches Claude Code requirements
# Run with: ./tests/validate-structure.sh
# Exit codes: 0 = all pass, 1 = failures

set -uo pipefail
# Note: not using -e so we can collect all failures

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SKILLS_DIR="$ROOT_DIR/skills"
COMMANDS_DIR="$ROOT_DIR/commands"
HOOKS_DIR="$ROOT_DIR/hooks"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS_COUNT++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL_COUNT++))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARN_COUNT++))
}

header() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " $1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ============================================================================
# TEST 1: Skills Structure
# Each skill must be a FOLDER containing SKILL.md (not a flat .md file)
# ============================================================================
test_skills_structure() {
    header "TEST: Skills Folder Structure"

    if [ ! -d "$SKILLS_DIR" ]; then
        fail "Skills directory does not exist: $SKILLS_DIR"
        return
    fi

    local skill_count=0
    local valid_count=0
    local flat_files=0

    # Check for flat .md files (WRONG structure)
    shopt -s nullglob
    for file in "$SKILLS_DIR"/*.md; do
        if [ -f "$file" ]; then
            flat_files=$((flat_files + 1))
            fail "Flat .md file found (should be folder): $(basename "$file")"
        fi
    done
    shopt -u nullglob

    if [ "$flat_files" -eq 0 ]; then
        pass "No flat .md files in skills/ (correct)"
    fi

    # Check for folders with SKILL.md (CORRECT structure)
    for skill_dir in "$SKILLS_DIR"/*/; do
        if [ -d "$skill_dir" ]; then
            skill_count=$((skill_count + 1))
            local skill_name=$(basename "$skill_dir")

            if [ -f "$skill_dir/SKILL.md" ]; then
                valid_count=$((valid_count + 1))
                pass "Skill '$skill_name' has SKILL.md"
            else
                fail "Skill '$skill_name' missing SKILL.md"
            fi
        fi
    done

    echo ""
    echo "Skills found: $skill_count folders, $flat_files flat files"

    if [ "$flat_files" -gt 0 ] && [ "$skill_count" -eq 0 ]; then
        fail "Skills use flat .md structure - must be folders with SKILL.md"
    fi
}

# ============================================================================
# TEST 2: SKILL.md YAML Frontmatter
# Each SKILL.md must have YAML frontmatter with 'name' and 'description'
# ============================================================================
test_skill_frontmatter() {
    header "TEST: SKILL.md YAML Frontmatter"

    for skill_dir in "$SKILLS_DIR"/*/; do
        if [ -d "$skill_dir" ] && [ -f "$skill_dir/SKILL.md" ]; then
            local skill_name=$(basename "$skill_dir")
            local skill_file="$skill_dir/SKILL.md"

            # Check for YAML frontmatter (starts with ---)
            if head -1 "$skill_file" | grep -q "^---$"; then
                # Extract frontmatter
                local frontmatter=$(sed -n '/^---$/,/^---$/p' "$skill_file" | head -20)

                # Check for 'name:' field
                if echo "$frontmatter" | grep -q "^name:"; then
                    pass "Skill '$skill_name' has 'name' field"
                else
                    fail "Skill '$skill_name' missing 'name' in frontmatter"
                fi

                # Check for 'description:' field
                if echo "$frontmatter" | grep -q "^description:"; then
                    pass "Skill '$skill_name' has 'description' field"
                else
                    fail "Skill '$skill_name' missing 'description' in frontmatter"
                fi
            else
                fail "Skill '$skill_name' missing YAML frontmatter (must start with ---)"
            fi
        fi
    done

    # Also check flat files that shouldn't exist
    shopt -s nullglob
    for file in "$SKILLS_DIR"/*.md; do
        if [ -f "$file" ]; then
            warn "Flat file '$(basename "$file")' cannot be validated (wrong structure)"
        fi
    done
    shopt -u nullglob
}

# ============================================================================
# TEST 3: Commands Structure
# Commands should be .md files in commands/
# ============================================================================
test_commands_structure() {
    header "TEST: Commands Structure"

    if [ ! -d "$COMMANDS_DIR" ]; then
        fail "Commands directory does not exist: $COMMANDS_DIR"
        return
    fi

    local cmd_count=0
    for cmd_file in "$COMMANDS_DIR"/*.md; do
        if [ -f "$cmd_file" ]; then
            cmd_count=$((cmd_count + 1))
            local cmd_name=$(basename "$cmd_file" .md)
            pass "Command found: $cmd_name"
        fi
    done

    if [ "$cmd_count" -eq 0 ]; then
        fail "No commands found in $COMMANDS_DIR"
    else
        echo ""
        echo "Total commands: $cmd_count"
    fi
}

# ============================================================================
# TEST 4: Hooks Structure (checks ALL hooks dynamically)
# ============================================================================
test_hooks_structure() {
    header "TEST: Hooks Structure"

    if [ ! -d "$HOOKS_DIR" ]; then
        warn "Hooks directory does not exist: $HOOKS_DIR"
        return
    fi

    local hook_count=0
    shopt -s nullglob
    for hook_file in "$HOOKS_DIR"/*; do
        if [ -f "$hook_file" ]; then
            hook_count=$((hook_count + 1))
            local hook_name=$(basename "$hook_file")

            pass "Hook found: $hook_name"

            if [ -x "$hook_file" ]; then
                pass "Hook '$hook_name' is executable"
            else
                fail "Hook '$hook_name' is NOT executable"
            fi

            # Check hook has shebang
            if head -1 "$hook_file" | grep -q "^#!"; then
                pass "Hook '$hook_name' has shebang"
            else
                warn "Hook '$hook_name' missing shebang"
            fi
        fi
    done
    shopt -u nullglob

    if [ "$hook_count" -eq 0 ]; then
        warn "No hooks found in $HOOKS_DIR"
    else
        echo ""
        echo "Total hooks: $hook_count"
    fi

    # Also check installed hooks
    local installed_hooks_dir="$HOME/.claude/hooks"
    if [ -d "$installed_hooks_dir" ]; then
        echo ""
        echo "Checking installed hooks (~/.claude/hooks/):"
        local installed_count=0
        for hook_file in "$installed_hooks_dir"/*; do
            if [ -f "$hook_file" ]; then
                installed_count=$((installed_count + 1))
                local hook_name=$(basename "$hook_file")
                if [ -x "$hook_file" ]; then
                    pass "Installed hook '$hook_name' is executable"
                else
                    fail "Installed hook '$hook_name' is NOT executable"
                fi
            fi
        done
        echo "Installed hooks: $installed_count"
    fi
}

# ============================================================================
# TEST 5: Install Script
# ============================================================================
test_install_script() {
    header "TEST: Install Script"

    if [ -f "$ROOT_DIR/install.sh" ]; then
        pass "install.sh exists"

        if [ -x "$ROOT_DIR/install.sh" ]; then
            pass "install.sh is executable"
        else
            fail "install.sh is not executable"
        fi

        # Check that it references correct structure
        if grep -q "SKILL.md" "$ROOT_DIR/install.sh"; then
            pass "install.sh references SKILL.md structure"
        else
            warn "install.sh may not handle SKILL.md structure"
        fi
    else
        fail "install.sh missing"
    fi
}

# ============================================================================
# TEST 6: Installed Skills (checks ~/.claude/skills/)
# ============================================================================
test_installed_skills() {
    header "TEST: Installed Skills (~/.claude/skills/)"

    local installed_dir="$HOME/.claude/skills"

    if [ ! -d "$installed_dir" ]; then
        warn "No skills installed at $installed_dir"
        return
    fi

    local folder_count=0
    local flat_count=0

    # Count folders with SKILL.md
    for skill_dir in "$installed_dir"/*/; do
        if [ -d "$skill_dir" ] && [ -f "$skill_dir/SKILL.md" ]; then
            folder_count=$((folder_count + 1))
        fi
    done

    # Count flat .md files
    shopt -s nullglob
    for file in "$installed_dir"/*.md; do
        if [ -f "$file" ]; then
            flat_count=$((flat_count + 1))
        fi
    done
    shopt -u nullglob

    if [ "$folder_count" -gt 0 ]; then
        pass "Found $folder_count properly structured skills"
    fi

    if [ "$flat_count" -gt 0 ]; then
        fail "Found $flat_count flat .md files (wrong structure)"
    fi

    echo ""
    echo "Installed: $folder_count folder skills, $flat_count flat files"
}

# ============================================================================
# TEST 7: README Documentation
# ============================================================================
test_readme() {
    header "TEST: README Documentation"

    if [ -f "$ROOT_DIR/README.md" ]; then
        pass "README.md exists"

        # Check for key sections
        if grep -q "Quick Start\|Quick Install" "$ROOT_DIR/README.md"; then
            pass "README has Quick Start section"
        else
            warn "README missing Quick Start section"
        fi

        if grep -q "Skills Included\|What's Included" "$ROOT_DIR/README.md"; then
            pass "README has Skills listing"
        else
            warn "README missing Skills listing"
        fi
    else
        fail "README.md missing"
    fi
}

# ============================================================================
# TEST 8: Scripts Structure
# ============================================================================
test_scripts_structure() {
    header "TEST: Scripts Structure"

    local scripts_dir="$ROOT_DIR/scripts"

    if [ ! -d "$scripts_dir" ]; then
        warn "Scripts directory does not exist: $scripts_dir"
        return
    fi

    local script_count=0
    shopt -s nullglob
    for script_file in "$scripts_dir"/*.sh; do
        if [ -f "$script_file" ]; then
            script_count=$((script_count + 1))
            local script_name=$(basename "$script_file")

            pass "Script found: $script_name"

            if [ -x "$script_file" ]; then
                pass "Script '$script_name' is executable"
            else
                fail "Script '$script_name' is NOT executable"
            fi
        fi
    done
    shopt -u nullglob

    if [ "$script_count" -eq 0 ]; then
        warn "No scripts found in $scripts_dir"
    else
        echo ""
        echo "Total scripts: $script_count"
    fi
}

# ============================================================================
# QUICK MODE - Essential checks only (for initialize-project)
# ============================================================================
quick_validate() {
    echo ""
    echo "🔍 Quick validation of Maggy installation..."
    echo ""

    local errors=0

    # Check skills directory exists and has content
    if [ -d "$HOME/.claude/skills" ]; then
        local skill_count=$(find "$HOME/.claude/skills" -maxdepth 1 -type d 2>/dev/null | wc -l)
        local flat_count=$(find "$HOME/.claude/skills" -maxdepth 1 -name "*.md" -type f 2>/dev/null | wc -l)

        if [ "$flat_count" -gt 0 ]; then
            echo -e "${RED}✗${NC} Skills use flat .md structure (need folder/SKILL.md)"
            errors=$((errors + 1))
        elif [ "$skill_count" -gt 1 ]; then
            echo -e "${GREEN}✓${NC} Skills installed ($((skill_count - 1)) skills)"
        else
            echo -e "${YELLOW}⚠${NC} No skills found in ~/.claude/skills/"
        fi
    else
        echo -e "${RED}✗${NC} Skills directory missing (~/.claude/skills/)"
        errors=$((errors + 1))
    fi

    # Check commands
    if [ -d "$HOME/.claude/commands" ]; then
        local cmd_count=$(find "$HOME/.claude/commands" -name "*.md" -type f 2>/dev/null | wc -l)
        if [ "$cmd_count" -gt 0 ]; then
            echo -e "${GREEN}✓${NC} Commands installed ($cmd_count commands)"
        else
            echo -e "${YELLOW}⚠${NC} No commands found"
        fi
    else
        echo -e "${RED}✗${NC} Commands directory missing (~/.claude/commands/)"
        errors=$((errors + 1))
    fi

    # Check hooks
    if [ -d "$HOME/.claude/hooks" ]; then
        local hook_count=$(find "$HOME/.claude/hooks" -type f 2>/dev/null | wc -l)
        if [ "$hook_count" -gt 0 ]; then
            echo -e "${GREEN}✓${NC} Hooks installed ($hook_count hooks)"
        else
            echo -e "${YELLOW}⚠${NC} No hooks found"
        fi
    else
        echo -e "${YELLOW}⚠${NC} Hooks directory missing (~/.claude/hooks/)"
    fi

    echo ""
    if [ "$errors" -gt 0 ]; then
        echo -e "${RED}Bootstrap has issues. Run full validation:${NC}"
        echo "  $ROOT_DIR/tests/validate-structure.sh"
        return 1
    else
        echo -e "${GREEN}Bootstrap installation OK${NC}"
        return 0
    fi
}

# ============================================================================
# MAIN
# ============================================================================
test_cross_tool_templates() {
    header "CROSS-TOOL TEMPLATES"

    # AGENTS.md template
    if [ -f "$ROOT_DIR/templates/AGENTS.md" ]; then
        pass "templates/AGENTS.md exists"
        if grep -q "## Skills" "$ROOT_DIR/templates/AGENTS.md"; then
            pass "AGENTS.md has Skills section"
        else
            fail "AGENTS.md missing Skills section"
        fi
    else
        fail "templates/AGENTS.md missing"
    fi

    # config.toml template
    if [ -f "$ROOT_DIR/templates/config.toml" ]; then
        pass "templates/config.toml exists"
        if grep -q '\[\[hooks\]\]' "$ROOT_DIR/templates/config.toml"; then
            pass "config.toml has [[hooks]] sections"
        else
            fail "config.toml missing [[hooks]] sections"
        fi
    else
        fail "templates/config.toml missing"
    fi

    # Cross-tool scripts
    for script in detect-agents.sh install-skills.sh; do
        if [ -f "$ROOT_DIR/scripts/$script" ]; then
            pass "scripts/$script exists"
            if [ -x "$ROOT_DIR/scripts/$script" ]; then
                pass "scripts/$script is executable"
            else
                fail "scripts/$script is not executable"
            fi
        else
            fail "scripts/$script missing"
        fi
    done

    # sync-agents command
    if [ -f "$ROOT_DIR/commands/sync-agents.md" ]; then
        pass "commands/sync-agents.md exists"
    else
        fail "commands/sync-agents.md missing"
    fi
}

# ============================================================================
show_help() {
    echo "Usage: $(basename "$0") [OPTIONS]"
    echo ""
    echo "Validates Maggy structure matches Claude Code requirements."
    echo ""
    echo "Options:"
    echo "  --quick     Quick validation (for initialize-project)"
    echo "  --full      Full validation (default)"
    echo "  --help      Show this help"
    echo ""
    echo "Exit codes:"
    echo "  0 = All validations passed"
    echo "  1 = Validation failures found"
}

main() {
    local mode="full"

    while [[ $# -gt 0 ]]; do
        case $1 in
            --quick|-q)
                mode="quick"
                shift
                ;;
            --full|-f)
                mode="full"
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    if [ "$mode" = "quick" ]; then
        quick_validate
        exit $?
    fi

    # Full validation
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║     MAGGY STRUCTURE VALIDATION                              ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Validating: $ROOT_DIR"

    test_skills_structure
    test_skill_frontmatter
    test_commands_structure
    test_hooks_structure
    test_scripts_structure
    test_install_script
    test_installed_skills
    test_readme
    test_cross_tool_templates

    header "SUMMARY"
    echo ""
    echo -e "${GREEN}Passed:${NC}  $PASS_COUNT"
    echo -e "${RED}Failed:${NC}  $FAIL_COUNT"
    echo -e "${YELLOW}Warnings:${NC} $WARN_COUNT"
    echo ""

    if [ "$FAIL_COUNT" -gt 0 ]; then
        echo -e "${RED}VALIDATION FAILED${NC} - $FAIL_COUNT issues need fixing"
        exit 1
    else
        echo -e "${GREEN}VALIDATION PASSED${NC}"
        exit 0
    fi
}

main "$@"
