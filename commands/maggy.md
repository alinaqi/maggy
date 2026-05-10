# /maggy — Launch Maggy Dashboard

Start Maggy (the AI engineering command center) and open the dashboard in a browser.

---

## Usage

`/maggy` — start server if not running, open dashboard
`/maggy stop` — stop running server
`/maggy status` — show whether server is running + config summary

---

## Steps

### 1. Check config

```bash
if [ ! -f ~/.maggy/config.yaml ]; then
  echo "Maggy not configured yet. Run /maggy-init first."
  exit 1
fi
```

### 2. Resolve host/port from config (don't hardcode 8080)

```bash
# Read dashboard.host and dashboard.port from ~/.maggy/config.yaml.
# Falls back to 127.0.0.1:8080 only if keys are missing.
HOST=$(python3 -c "import yaml; d=yaml.safe_load(open('$HOME/.maggy/config.yaml'))or{}; print((d.get('dashboard') or {}).get('host') or '127.0.0.1')")
PORT=$(python3 -c "import yaml; d=yaml.safe_load(open('$HOME/.maggy/config.yaml'))or{}; print((d.get('dashboard') or {}).get('port') or 8080)")
URL="http://${HOST}:${PORT}"
```

### 3. Check if already running

```bash
if curl -sf "${URL}/api/health" >/dev/null 2>&1; then
  echo "Maggy is already running at ${URL}"
  open "${URL}" 2>/dev/null || xdg-open "${URL}" 2>/dev/null || true
  exit 0
fi
```

### 4. Start in background

The Maggy install lives at `<bootstrap-root>/maggy`. Resolve it from `~/.claude/.bootstrap-dir`:

```bash
BOOTSTRAP_DIR=$(cat ~/.claude/.bootstrap-dir 2>/dev/null || echo "")
MAGGY_DIR="$BOOTSTRAP_DIR/maggy"

if [ ! -d "$MAGGY_DIR" ]; then
  echo "Maggy not installed. Run: cd <maggy>/maggy && ./install.sh"
  exit 1
fi

cd "$MAGGY_DIR"
mkdir -p "$HOME/.maggy"
nohup python3 -m maggy.main > "$HOME/.maggy/maggy.log" 2>&1 &
echo $! > "$HOME/.maggy/maggy.pid"
```

### 5. Wait for health check

```bash
for i in {1..15}; do
  if curl -sf "${URL}/api/health" >/dev/null 2>&1; then
    echo "✓ Maggy ready at ${URL}"
    open "${URL}" 2>/dev/null || true
    exit 0
  fi
  sleep 1
done
echo "Maggy didn't come up in 15s. Check ~/.maggy/maggy.log"
```

### 5. Report status

Show:
```
Maggy is running:
  Dashboard: http://127.0.0.1:8080
  Logs: ~/.maggy/maggy.log
  PID: <pid>
```

---

## Related

- `/maggy-init` — first-time setup wizard
- `/icpg-bootstrap` — Maggy's Execute button uses iCPG context from this
