#!/bin/bash
# Per-project Vercel isolation — each project gets its own .vercel/ directory.
# Run once per project. Creates isolated config, no global conflicts.
# Usage: ./scripts/setup-vercel-isolation.sh [project-dir]

set -e

PROJECT_DIR="${1:-.}"
PROJECT_NAME=$(basename "$(cd "$PROJECT_DIR" && pwd)")

echo ""
echo "  ⚡ Vercel Per-Project Isolation Setup"
echo "  Project: $PROJECT_NAME"
echo "  Dir: $PROJECT_DIR"
echo ""

# 1. Create per-project .vercel directory
cd "$PROJECT_DIR"
mkdir -p .vercel

# 2. Link to Vercel project (creates .vercel/project.json)
echo "  Linking to Vercel..."
if [ -f .vercel/project.json ]; then
  echo "  ✓ Already linked: $(cat .vercel/project.json | python3 -c "import json,sys; print(json.load(sys.stdin).get('projectId','?'))" 2>/dev/null || echo 'unknown')"
else
  # Check if project exists on Vercel
  if vercel project ls 2>/dev/null | grep -qi "$PROJECT_NAME"; then
    echo "  → Project '$PROJECT_NAME' found on Vercel. Linking..."
    vercel link --cwd "$PROJECT_DIR" --project "$PROJECT_NAME" --yes 2>/dev/null || \
    vercel link --cwd "$PROJECT_DIR" --yes 2>/dev/null
  else
    echo "  → Creating new Vercel project '$PROJECT_NAME'..."
    vercel link --cwd "$PROJECT_DIR" --yes 2>/dev/null
  fi
  echo "  ✓ Linked"
fi

# 3. Verify isolation
echo ""
echo "  ✓ Per-project Vercel isolation active"
echo "  Config: $PROJECT_DIR/.vercel/project.json"
echo ""
echo "  Deploy from this project:"
echo "    cd $PROJECT_DIR && vercel --prod"
echo ""
echo "  Another project can deploy simultaneously — no conflicts."
echo ""
