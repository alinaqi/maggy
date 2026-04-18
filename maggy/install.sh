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

# 1. Check Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 not found. Install Python 3.11 or later first."
  exit 1
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
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

# 4. Config directory + template
mkdir -p "$MAGGY_HOME"
if [ ! -f "$MAGGY_HOME/config.yaml" ]; then
  cp "$HERE/config.example.yaml" "$MAGGY_HOME/config.yaml"
  echo "✓ Wrote config template to $MAGGY_HOME/config.yaml"
  NEEDS_CONFIG=1
else
  echo "✓ Config already exists at $MAGGY_HOME/config.yaml (not overwritten)"
  NEEDS_CONFIG=0
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
if [ "$NEEDS_CONFIG" = "1" ]; then
  echo "Next steps:"
  echo "  1. Edit $MAGGY_HOME/config.yaml"
  echo "     - Set your org name, domain, GitHub org + repos"
  echo "     - Set codebase paths for each repo you want Maggy to execute in"
  echo
  echo "  2. Export credentials:"
  echo "     export GITHUB_TOKEN=ghp_...           # repo + issues scopes"
  echo "     export ANTHROPIC_API_KEY=sk-ant-..."
  echo
  echo "  3. Run:"
  echo "     cd $HERE && python3 -m src.main"
  echo
  echo "  4. Open http://localhost:8080"
else
  echo "Ready to run:"
  echo "  cd $HERE && python3 -m src.main"
  echo "  Then open http://localhost:8080"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
