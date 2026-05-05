#!/bin/bash
# detect-agents.sh - Detect installed AI CLI tools
# Output: newline-separated list of detected tools (claude, kimi, codex)
# Usage: ./detect-agents.sh
#        AGENTS=$(./detect-agents.sh)

set -euo pipefail

detect_by_binary() {
    local name="$1"
    local binary="$2"
    command -v "$binary" &>/dev/null && echo "$name"
}

detect_by_config() {
    local name="$1"
    local dir="$2"
    [ -d "$dir" ] && echo "$name"
}

detect_tool() {
    local name="$1"
    local binary="$2"
    local config_dir="$3"
    # Binary takes priority, config dir as fallback
    if command -v "$binary" &>/dev/null; then
        echo "$name"
    elif [ -d "$config_dir" ]; then
        echo "$name"
    fi
}

main() {
    detect_tool "claude" "claude" "$HOME/.claude"
    detect_tool "kimi" "kimi" "$HOME/.kimi"
    detect_tool "codex" "codex" "$HOME/.codex"

    # Container runtime
    command -v docker &>/dev/null && echo "docker" || true
    command -v orbctl &>/dev/null && echo "orbstack" || true

    # Polyphony orchestrator
    command -v polyphony &>/dev/null && echo "polyphony" || true
}

main
