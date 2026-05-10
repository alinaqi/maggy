#!/usr/bin/env bash
# Run behavioral evals for Maggy skills.
#
# Usage:
#   ./run-evals.sh                   # Run all evals
#   ./run-evals.sh base              # Run evals for a specific skill
#   ./run-evals.sh --baseline base   # Run with baseline comparison
#
# Requires: tessl CLI (https://tessl.io)

set -euo pipefail

EVALS_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$(dirname "$EVALS_DIR")/skills"

BASELINE=false
SKILL_FILTER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --baseline)
            BASELINE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--baseline] [SKILL_NAME]"
            echo ""
            echo "Options:"
            echo "  --baseline    Compare with/without skill loaded"
            echo "  SKILL_NAME    Run evals for a specific skill only"
            exit 0
            ;;
        *)
            SKILL_FILTER="$1"
            shift
            ;;
    esac
done

# Check tessl is installed
if ! command -v tessl &>/dev/null; then
    echo "Error: tessl CLI not found. Install from https://tessl.io"
    exit 1
fi

RESULTS_DIR="$EVALS_DIR/.results"
mkdir -p "$RESULTS_DIR"

PASS=0
FAIL=0
SKIP=0

for scenario_dir in "$EVALS_DIR"/*/scenario-*; do
    [ -d "$scenario_dir" ] || continue

    skill_name="$(basename "$(dirname "$scenario_dir")")"

    # Apply filter
    if [[ -n "$SKILL_FILTER" && "$skill_name" != "$SKILL_FILTER" ]]; then
        continue
    fi

    scenario_name="$(basename "$scenario_dir")"
    task_file="$scenario_dir/task.md"
    criteria_file="$scenario_dir/criteria.json"

    if [[ ! -f "$task_file" || ! -f "$criteria_file" ]]; then
        echo "SKIP $skill_name/$scenario_name (missing task.md or criteria.json)"
        ((SKIP++))
        continue
    fi

    echo "--- $skill_name/$scenario_name ---"

    result_file="$RESULTS_DIR/${skill_name}_${scenario_name}.json"

    if $BASELINE; then
        echo "  Running WITHOUT skill..."
        tessl eval run \
            --task "$task_file" \
            --criteria "$criteria_file" \
            --output "$RESULTS_DIR/${skill_name}_${scenario_name}_baseline.json" \
            2>&1 | sed 's/^/  /' || true

        echo "  Running WITH skill..."
        tessl eval run \
            --task "$task_file" \
            --criteria "$criteria_file" \
            --skill "$SKILLS_DIR/$skill_name" \
            --output "$result_file" \
            2>&1 | sed 's/^/  /' || true
    else
        tessl eval run \
            --task "$task_file" \
            --criteria "$criteria_file" \
            --skill "$SKILLS_DIR/$skill_name" \
            --output "$result_file" \
            2>&1 | sed 's/^/  /' || true
    fi

    if [[ -f "$result_file" ]]; then
        ((PASS++))
    else
        ((FAIL++))
    fi
done

echo ""
echo "=== Eval Summary ==="
echo "Pass: $PASS  Fail: $FAIL  Skip: $SKIP"
