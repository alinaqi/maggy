#!/bin/bash

# install-graph-tools.sh - Install code graph MCP servers
#
# Tier 1: codebase-memory-mcp (default, always installed)
#   - Single static binary, zero dependencies
#   - 64 languages, sub-ms queries, 14 MCP tools
#
# Tier 2: Joern CPG via CodeBadger (opt-in, --joern)
#   - Full CPG: AST + CFG + CDG + DDG + PDG
#   - Requires Docker + Python 3.10+
#
# Tier 3: CodeQL (opt-in, --codeql)
#   - Interprocedural taint analysis, security queries
#   - Requires CodeQL CLI

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
INSTALL_JOERN=false
INSTALL_CODEQL=false
INSTALL_DIR="$HOME/.local/bin"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --joern) INSTALL_JOERN=true; shift ;;
        --codeql) INSTALL_CODEQL=true; shift ;;
        --all) INSTALL_JOERN=true; INSTALL_CODEQL=true; shift ;;
        --help|-h)
            echo "Usage: install-graph-tools.sh [OPTIONS]"
            echo ""
            echo "Install code graph MCP servers for Maggy."
            echo ""
            echo "Options:"
            echo "  (no flags)   Install Tier 1 only (codebase-memory-mcp)"
            echo "  --joern      Also install Tier 2 (Joern CPG via CodeBadger)"
            echo "  --codeql     Also install Tier 3 (CodeQL)"
            echo "  --all        Install all tiers"
            echo "  --help       Show this help"
            echo ""
            echo "Tiers:"
            echo "  1  codebase-memory-mcp  AST graph, 64 langs, sub-ms     (always)"
            echo "  2  Joern/CodeBadger     Full CPG (AST+CFG+PDG), 12 langs (opt-in)"
            echo "  3  CodeQL               Taint analysis, security, 10+ langs (opt-in)"
            exit 0
            ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; echo "Run with --help for usage."; exit 1 ;;
    esac
done

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Code Graph Tools Installer"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Detect platform
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
case "$ARCH" in
    aarch64|arm64) ARCH="arm64" ;;
    x86_64|amd64) ARCH="amd64" ;;
esac

echo -e "${BLUE}Platform: ${OS}-${ARCH}${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────
# Tier 1: codebase-memory-mcp
# ─────────────────────────────────────────────────────────────────
echo "── Tier 1: codebase-memory-mcp ──────────────────────────────"
echo ""

mkdir -p "$INSTALL_DIR"

if command -v codebase-memory-mcp &> /dev/null; then
    echo -e "${GREEN}✓ codebase-memory-mcp already installed${NC}"
    codebase-memory-mcp --version 2>/dev/null || true
else
    DOWNLOAD_URL="https://github.com/DeusData/codebase-memory-mcp/releases/latest/download/codebase-memory-mcp-${OS}-${ARCH}.tar.gz"
    TEMP_DIR=$(mktemp -d)

    echo "Downloading from GitHub releases..."
    echo "  URL: $DOWNLOAD_URL"

    if curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_DIR/codebase-memory-mcp.tar.gz"; then
        tar xzf "$TEMP_DIR/codebase-memory-mcp.tar.gz" -C "$TEMP_DIR"
        mv "$TEMP_DIR/codebase-memory-mcp" "$INSTALL_DIR/codebase-memory-mcp"
        chmod +x "$INSTALL_DIR/codebase-memory-mcp"
        echo -e "${GREEN}✓ Installed codebase-memory-mcp to $INSTALL_DIR${NC}"

        # Auto-configure for Claude Code and other agents
        echo ""
        echo "Running auto-configuration..."
        "$INSTALL_DIR/codebase-memory-mcp" install 2>/dev/null || true
    else
        echo -e "${RED}✗ Failed to download codebase-memory-mcp${NC}"
        echo ""
        echo "  Manual install:"
        echo "  1. Go to https://github.com/DeusData/codebase-memory-mcp/releases"
        echo "  2. Download codebase-memory-mcp-${OS}-${ARCH}.tar.gz"
        echo "  3. Extract and move to $INSTALL_DIR/"
        echo "  4. Run: codebase-memory-mcp install"
    fi

    rm -rf "$TEMP_DIR"
fi

# Check PATH
if ! echo "$PATH" | tr ':' '\n' | grep -q "$INSTALL_DIR"; then
    echo ""
    echo -e "${YELLOW}⚠ $INSTALL_DIR is not in your PATH${NC}"
    echo "  Add to your shell profile:"
    echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
fi

# ─────────────────────────────────────────────────────────────────
# Tier 2: Joern CPG via CodeBadger (opt-in)
# ─────────────────────────────────────────────────────────────────
if [ "$INSTALL_JOERN" = true ]; then
    echo ""
    echo "── Tier 2: Joern CPG (CodeBadger) ───────────────────────────"
    echo ""

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker not found${NC}"
        echo "  Joern requires Docker. Install from: https://docker.com"
        echo "  Skipping Tier 2 installation."
    elif ! docker info &> /dev/null 2>&1; then
        echo -e "${RED}✗ Docker is not running${NC}"
        echo "  Start Docker Desktop and try again."
        echo "  Skipping Tier 2 installation."
    else
        echo -e "${GREEN}✓ Docker is running${NC}"

        # Check Python
        PYTHON_CMD=""
        if command -v python3 &> /dev/null; then
            PYTHON_CMD="python3"
        elif command -v python &> /dev/null; then
            PYTHON_CMD="python"
        fi

        if [ -z "$PYTHON_CMD" ]; then
            echo -e "${RED}✗ Python 3.10+ not found${NC}"
            echo "  Install Python: https://python.org"
            echo "  Skipping Tier 2 installation."
        else
            PY_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            echo -e "${GREEN}✓ Python $PY_VERSION found${NC}"

            CODEBADGER_DIR="$HOME/.claude/tools/codebadger"

            if [ -d "$CODEBADGER_DIR" ]; then
                echo -e "${GREEN}✓ CodeBadger already cloned${NC}"
                echo "  Pulling latest..."
                git -C "$CODEBADGER_DIR" pull 2>/dev/null || true
            else
                echo "Cloning CodeBadger..."
                mkdir -p "$HOME/.claude/tools"
                git clone https://github.com/lekssays/joern-mcp.git "$CODEBADGER_DIR" 2>/dev/null || {
                    echo -e "${RED}✗ Failed to clone CodeBadger${NC}"
                    echo "  Manual install: https://github.com/lekssays/joern-mcp"
                }
            fi

            if [ -d "$CODEBADGER_DIR" ]; then
                echo "Installing Python dependencies..."
                $PYTHON_CMD -m pip install -r "$CODEBADGER_DIR/requirements.txt" --quiet 2>/dev/null || true

                echo "Starting Joern Docker services..."
                (cd "$CODEBADGER_DIR" && docker compose up -d 2>/dev/null) || {
                    echo -e "${YELLOW}⚠ Docker compose failed. You may need to start manually:${NC}"
                    echo "  cd $CODEBADGER_DIR && docker compose up -d"
                }

                echo -e "${GREEN}✓ Joern/CodeBadger installed${NC}"
                echo ""
                echo "  To start the MCP server:"
                echo "  cd $CODEBADGER_DIR && $PYTHON_CMD main.py"
                echo ""
                echo "  MCP endpoint: http://localhost:4242/mcp"
            fi
        fi
    fi
fi

# ─────────────────────────────────────────────────────────────────
# Tier 3: CodeQL (opt-in)
# ─────────────────────────────────────────────────────────────────
if [ "$INSTALL_CODEQL" = true ]; then
    echo ""
    echo "── Tier 3: CodeQL ───────────────────────────────────────────"
    echo ""

    if command -v codeql &> /dev/null; then
        echo -e "${GREEN}✓ CodeQL already installed${NC}"
        codeql version 2>/dev/null || true
    else
        if command -v brew &> /dev/null; then
            echo "Installing CodeQL via Homebrew..."
            brew install codeql 2>/dev/null || {
                echo -e "${YELLOW}⚠ brew install codeql failed${NC}"
                echo "  Trying GitHub release download..."
            }
        fi

        # Fallback: direct download
        if ! command -v codeql &> /dev/null; then
            echo "Downloading CodeQL CLI..."
            echo ""
            echo "  Manual install from:"
            echo "  https://github.com/github/codeql-cli-binaries/releases"
            echo ""
            echo "  After download:"
            echo "  1. Extract to $INSTALL_DIR/codeql/"
            echo "  2. Add to PATH: export PATH=\"$INSTALL_DIR/codeql:\$PATH\""
        fi
    fi

    if command -v codeql &> /dev/null; then
        echo ""
        echo "Installing CodeQL query packs..."
        codeql pack download codeql/javascript-queries 2>/dev/null || true
        codeql pack download codeql/python-queries 2>/dev/null || true
        codeql pack download codeql/java-queries 2>/dev/null || true
        codeql pack download codeql/go-queries 2>/dev/null || true
        echo -e "${GREEN}✓ CodeQL query packs installed${NC}"
    fi
fi

# ─────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Installation Summary"
echo "════════════════════════════════════════════════════════════════"
echo ""

if command -v codebase-memory-mcp &> /dev/null; then
    echo -e "  ${GREEN}✓ Tier 1: codebase-memory-mcp (AST graph, 64 langs)${NC}"
else
    echo -e "  ${RED}✗ Tier 1: codebase-memory-mcp NOT installed${NC}"
fi

if [ "$INSTALL_JOERN" = true ]; then
    if [ -d "$HOME/.claude/tools/codebadger" ]; then
        echo -e "  ${GREEN}✓ Tier 2: Joern CPG via CodeBadger${NC}"
    else
        echo -e "  ${RED}✗ Tier 2: Joern NOT installed${NC}"
    fi
fi

if [ "$INSTALL_CODEQL" = true ]; then
    if command -v codeql &> /dev/null; then
        echo -e "  ${GREEN}✓ Tier 3: CodeQL${NC}"
    else
        echo -e "  ${RED}✗ Tier 3: CodeQL NOT installed${NC}"
    fi
fi

echo ""
echo "Next steps:"
echo "  1. Run /initialize-project in your project"
echo "  2. The MCP servers will be auto-configured in .mcp.json"
echo "  3. Claude will use the graph for optimized code navigation"
echo ""
