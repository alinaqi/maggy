#!/bin/bash
# Maggy + Claude Bootstrap Onboarding — collect API keys, enable/disable models.
# Run: ./scripts/onboard.sh

set -e

echo ""
echo "  ⚡ Maggy + Claude Bootstrap — Model Onboarding"
echo "  ─────────────────────────────────────────────"
echo ""
echo "  I'll ask you for API keys. Press Enter to skip any provider."
echo "  Models with skipped keys will be disabled for routing."
echo ""

ZSRC="$HOME/.zshrc"
# Markers for idempotent writes
MARKER_START="# >>> maggy-onboard-start (do not remove)"
MARKER_END="# <<< maggy-onboard-end"

# ── Collect keys ─────────────────────────────────────────────────────────

echo "  ┌─ DeepSeek V4 (Anthropic-compatible API)"
read -rsp "  │  API Key (sk-...): " DS_KEY
echo ""
if [ -n "$DS_KEY" ]; then
  DEEPSEEK_ENABLED=1
  echo "  │  → DeepSeek Flash + Pro enabled"
else
  DEEPSEEK_ENABLED=0
  echo "  │  → DeepSeek disabled (no key)"
fi
echo "  └────────────────────"

echo ""
echo "  ┌─ Google Gemini (OpenAI-compatible endpoint)"
read -rsp "  │  API Key: " GM_KEY
echo ""
if [ -n "$GM_KEY" ]; then
  GEMINI_ENABLED=1
  echo "  │  → Gemini Flash-Lite, Flash + Pro Search enabled"
else
  GEMINI_ENABLED=0
  echo "  │  → Gemini disabled (no key)"
fi
echo "  └────────────────────"

echo ""
echo "  ┌─ OpenAI (for Codex CLI)"
read -rsp "  │  API Key (sk-...): " OAI_KEY
echo ""
if [ -n "$OAI_KEY" ]; then
  CODEX_ENABLED=1
  echo "  │  → Codex enabled"
else
  CODEX_ENABLED=0
  echo "  │  → Codex disabled (no key)"
fi
echo "  └────────────────────"

echo ""
echo "  ┌─ Local Models"
echo -n "  │  Is Ollama running locally? [Y/n]: "
read -r OLLAMA_OK
if [[ "$OLLAMA_OK" =~ ^[Nn] ]]; then
  LOCAL_ENABLED=0
  echo "  │  → Qwen3 local disabled. Classifier will use kimi → deepseek."
else
  LOCAL_ENABLED=1
  echo "  │  → Qwen3 local enabled (fast + free classification)"
fi
echo "  └────────────────────"

# ── Write to ~/.zshrc ────────────────────────────────────────────────────

echo ""
echo "  Writing keys to $ZSRC..."

# Remove previous onboarding block if exists
if grep -q "$MARKER_START" "$ZSRC" 2>/dev/null; then
  sed -i '' "/$MARKER_START/,/$MARKER_END/d" "$ZSRC"
fi

{
  echo "$MARKER_START"
  echo "# Maggy Model Routing — API Keys (added by onboard.sh)"
  if [ "$DEEPSEEK_ENABLED" -eq 1 ]; then
    echo "export DEEPSEEK_API_KEY=\"$DS_KEY\""
  fi
  if [ "$GEMINI_ENABLED" -eq 1 ]; then
    echo "export GEMINI_API_KEY=\"$GM_KEY\""
  fi
  if [ "$CODEX_ENABLED" -eq 1 ]; then
    echo "export OPENAI_API_KEY=\"$OAI_KEY\""
  fi
  echo "$MARKER_END"
} >> "$ZSRC"

# ── Write routing config ──────────────────────────────────────────────────

CONFIG_DIR="$HOME/.claude"
mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_DIR/model-config.json" <<EOF
{
  "enabled": {
    "qwen3": $LOCAL_ENABLED,
    "deepseek-flash": $DEEPSEEK_ENABLED,
    "deepseek-pro": $DEEPSEEK_ENABLED,
    "gemini-flash-lite": $GEMINI_ENABLED,
    "gemini-flash": $GEMINI_ENABLED,
    "gemini-pro-search": $GEMINI_ENABLED,
    "kimi": 1,
    "codex": $CODEX_ENABLED,
    "claude": 1
  },
  "configured_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "  ✓ Model config written to $CONFIG_DIR/model-config.json"

# ── Summary ───────────────────────────────────────────────────────────────

ACTIVE=0
TOTAL=9
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║         Routing Status              ║"
echo "  ╠══════════════════════════════════════╣"

status_line() {
  local name="$1" enabled="$2" cost="$3"
  if [ "$enabled" -eq 1 ]; then
    printf "  ║  \033[32m✓\033[0m %-22s %12s  ║\n" "$name" "$cost"
    ACTIVE=$((ACTIVE + 1))
  else
    printf "  ║  \033[31m✗\033[0m %-22s %12s  ║\n" "$name" "(disabled)"
  fi
}

status_line "Qwen3 (local)" "$LOCAL_ENABLED" "$0"
status_line "DeepSeek Flash" "$DEEPSEEK_ENABLED" "$0.14/M"
status_line "DeepSeek Pro" "$DEEPSEEK_ENABLED" "$0.44/M"
status_line "Gemini Flash-Lite" "$GEMINI_ENABLED" "$0.10/M"
status_line "Gemini Flash" "$GEMINI_ENABLED" "$0.15/M"
status_line "Gemini Pro Search" "$GEMINI_ENABLED" "$1.25/M"
status_line "Kimi K2.6" 1 "$0.60/M"
status_line "Codex" "$CODEX_ENABLED" "varies"
status_line "Claude" 1 "$3-5/M"

echo "  ╠══════════════════════════════════════╣"
printf "  ║  %d of %d models active              ║\n" "$ACTIVE" "$TOTAL"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  To apply: source ~/.zshrc"
echo "  To re-configure: ./scripts/onboard.sh"
echo ""
