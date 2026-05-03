#!/bin/bash
# install-skills.sh - Install skills to any agent tool directory
# Usage: install-skills.sh <target_dir> [source_dir]
# Example: install-skills.sh ~/.kimi/skills
#          install-skills.sh ~/.codex/skills /path/to/skills

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_SOURCE="$SCRIPT_DIR/../skills"

usage() {
    echo "Usage: install-skills.sh <target_dir> [source_dir]"
    echo "  target_dir: Where to install skills"
    echo "  source_dir: Source skills (default: repo skills/)"
    exit 1
}

copy_skills() {
    local source="$1"
    local target="$2"
    local count=0

    mkdir -p "$target"
    for skill_dir in "$source"/*/; do
        [ -d "$skill_dir" ] || continue
        [ -f "$skill_dir/SKILL.md" ] || continue
        local name
        name=$(basename "$skill_dir")
        cp -r "${skill_dir%/}" "$target/"
        count=$((count + 1))
    done
    echo "$count"
}

main() {
    local target="${1:-}"
    local source="${2:-$DEFAULT_SOURCE}"

    [ -z "$target" ] && usage
    [ -d "$source" ] || {
        echo "Error: source dir '$source' not found" >&2
        exit 1
    }

    local installed
    installed=$(copy_skills "$source" "$target")
    echo "Installed $installed skills to $target"
}

main "$@"
