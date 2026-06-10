#!/bin/bash
# Consolidated test runner for autonomous agent modules (Phases 1-5)
set -e

cd "$(dirname "$0")/.."

echo "═══ Autonomous Agent Test Suite ═══"
echo ""

python3 -m pytest \
  tests/test_tool_schema.py \
  tests/test_tool_sandbox.py \
  tests/test_tool_parser.py \
  tests/test_tool_handlers.py \
  tests/test_tool_executor.py \
  tests/test_steering.py \
  tests/test_selective_skills.py \
  tests/test_approval.py \
  tests/test_execution_contracts.py \
  tests/test_routes_approval.py \
  tests/test_pi_tool_wiring.py \
  tests/test_agent_prompt.py \
  tests/test_e2e_autonomous.py \
  -v --tb=short 2>&1

echo ""
echo "═══ Done ═══"
