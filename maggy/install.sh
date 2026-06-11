#!/usr/bin/env bash
# Maggy installer — sets up deps and copies config template.
#
# Usage: ./install.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAGGY_HOME="${MAGGY_HOME:-$HOME/.maggy}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Maggy — Generic AI Engineering Command Center"
echo "  Installing to: $MAGGY_HOME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# 1. Check Python — enforce the 3.11+ minimum from pyproject.toml's requires-python.
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 not found. Install Python 3.11 or later first."
  exit 1
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "❌ Python 3.11 or later is required. Found Python $PY_VERSION."
  echo "   Install a newer Python (e.g. via pyenv, homebrew, or python.org)."
  exit 1
fi
echo "✓ Python $PY_VERSION"

# 2. Check claude CLI
if ! command -v claude >/dev/null 2>&1; then
  echo "⚠  claude CLI not found on PATH. Maggy can still run, but Execute won't work until you install Claude Code."
else
  echo "✓ claude CLI found"
fi

# 3. Install Python deps
echo
echo "Installing Python dependencies..."
python3 -m pip install --upgrade pip >/dev/null 2>&1 || true
python3 -m pip install -e "$HERE" || python3 -m pip install -r "$HERE/requirements.txt" 2>/dev/null || {
  # Fallback: explicit install of runtime deps
  python3 -m pip install 'fastapi>=0.115' 'uvicorn[standard]>=0.30' 'httpx>=0.27' 'anthropic>=0.40' 'pyyaml>=6.0' 'feedparser>=6.0' 'pydantic>=2.6'
}
echo "✓ Dependencies installed"

# 4. Config directory — Maggy AUTO-CONFIGURES from your local repos on first
#    run (no placeholder template, no hand-editing). See config.example.yaml
#    only if you want to customize later.
mkdir -p "$MAGGY_HOME"
if [ -f "$MAGGY_HOME/config.yaml" ]; then
  echo "✓ Config exists at $MAGGY_HOME/config.yaml (not overwritten)"
else
  echo "✓ Maggy will auto-configure from your local repos on first run"
fi

# 5. Remember bootstrap location for iCPG integration
BOOTSTRAP_MARKER="$HOME/.claude/.bootstrap-dir"
if [ ! -f "$BOOTSTRAP_MARKER" ]; then
  mkdir -p "$HOME/.claude"
  # Maggy lives in <bootstrap>/maggy — one level up is bootstrap root
  echo "$(cd "$HERE/.." && pwd)" > "$BOOTSTRAP_MARKER"
  echo "✓ Marked bootstrap location for iCPG access"
fi

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Ready. Maggy auto-configures from your local repos on first run."
echo
echo "  Run:   maggy serve        (or: cd $HERE && python3 -m maggy.main)"
echo "  Open:  http://localhost:8080"
echo
echo "Optional (not needed to start — local mode works without them):"
echo "  export GITHUB_TOKEN=ghp_...       # GitHub issue sync"
echo "  export ANTHROPIC_API_KEY=sk-ant-... # API-model features"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
