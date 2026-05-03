#!/bin/bash
# convert-hooks-to-toml.sh - Convert settings.json hooks to config.toml format
# Usage: convert-hooks-to-toml.sh [settings.json] > config.toml
# Requires: jq

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_INPUT="$SCRIPT_DIR/../templates/settings.json"

check_deps() {
    command -v jq &>/dev/null || {
        echo "Error: jq is required" >&2
        exit 1
    }
}

print_header() {
    cat <<'HEADER'
# Agent CLI Configuration
# Compatible with Kimi CLI and OpenAI Codex CLI
# Auto-generated from settings.json hooks
HEADER
    echo ""
}

extract_hook() {
    local event="$1"
    local matcher="$2"
    local command="$3"
    local timeout="$4"

    echo "[[hooks]]"
    echo "event = \"$event\""
    [ -n "$matcher" ] && echo "matcher = \"$matcher\""
    echo "command = \"\"\""
    echo "$command"
    echo "\"\"\""
    echo "timeout = $timeout"
    echo ""
}

convert_event() {
    local input="$1"
    local event="$2"
    local entries

    entries=$(jq -c ".hooks.${event}[]?" "$input" 2>/dev/null) || return 0

    echo "$entries" | while IFS= read -r entry; do
        local matcher
        matcher=$(echo "$entry" | jq -r '.matcher // ""')
        local hooks_array
        hooks_array=$(echo "$entry" | jq -c '.hooks[]')

        echo "$hooks_array" | while IFS= read -r hook; do
            local cmd timeout
            cmd=$(echo "$hook" | jq -r '.command')
            timeout=$(echo "$hook" | jq -r '.timeout // 30')
            extract_hook "$event" "$matcher" "$cmd" "$timeout"
        done
    done
}

main() {
    local input="${1:-$DEFAULT_INPUT}"
    [ -f "$input" ] || {
        echo "Error: '$input' not found" >&2
        exit 1
    }

    check_deps
    print_header

    local events=(
        "PreCompact" "PreToolUse" "PostToolUse"
        "Stop" "SessionStart" "SessionEnd"
    )
    for event in "${events[@]}"; do
        convert_event "$input" "$event"
    done
}

main "$@"
