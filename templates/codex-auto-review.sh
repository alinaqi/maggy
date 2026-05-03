#!/bin/bash
# codex-auto-review.sh — Stop hook: auto-review with Codex after tests pass
# Exit 0 = pass (no issues or codex not installed)
# Exit 2 = critical/high issues found (feeds back to Claude)
#
# Install: copy to .claude/scripts/codex-auto-review.sh
# Requires: codex CLI (npm i -g @openai/codex)

set -uo pipefail

REVIEW_FILE="/tmp/codex-review-$$.txt"

check_codex() {
    command -v codex &>/dev/null
}

get_changed_files() {
    git diff --name-only HEAD 2>/dev/null
    git diff --cached --name-only 2>/dev/null
}

has_changes() {
    local files
    files=$(get_changed_files | sort -u | grep -cE '\.(ts|tsx|js|jsx|py|go|rs|java|kt)$' || true)
    [ "$files" -gt 0 ]
}

run_codex_review() {
    local diff_content
    diff_content=$(git diff HEAD 2>/dev/null; git diff --cached 2>/dev/null)
    [ -z "$diff_content" ] && return 0

    # Truncate diff to avoid token limits (keep first 8000 chars)
    local truncated
    truncated=$(echo "$diff_content" | head -c 8000)

    codex exec \
        --full-auto \
        --sandbox read-only \
        --output-last-message "$REVIEW_FILE" \
        "Review this diff for critical bugs and security issues only. Be concise. Flag only Critical or High severity: $truncated" \
        2>/dev/null
}

check_findings() {
    [ -f "$REVIEW_FILE" ] || return 0

    if grep -qiE 'critical|🔴|security vulnerability|injection' "$REVIEW_FILE"; then
        echo "CODEX AUTO-REVIEW: Critical issues found:" >&2
        cat "$REVIEW_FILE" >&2
        rm -f "$REVIEW_FILE"
        return 2
    fi

    if grep -qiE '🟠|high severity' "$REVIEW_FILE"; then
        echo "CODEX AUTO-REVIEW: High severity issues:" >&2
        cat "$REVIEW_FILE" >&2
        rm -f "$REVIEW_FILE"
        return 2
    fi

    rm -f "$REVIEW_FILE"
    return 0
}

main() {
    # Skip if codex not installed
    check_codex || exit 0

    # Skip if no code changes
    has_changes || exit 0

    # Run review
    run_codex_review || exit 0

    # Check for critical/high findings
    check_findings
    exit $?
}

main
