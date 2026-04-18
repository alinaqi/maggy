# /maggy — Launch Maggy Dashboard

Start Maggy (the AI engineering command center that ships with claude-bootstrap) and open the dashboard in a browser.

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

### 2. Check if already running

```bash
if curl -sf http://127.0.0.1:8080/api/health >/dev/null 2>&1; then
  echo "Maggy is already running at http://127.0.0.1:8080"
  open http://127.0.0.1:8080 2>/dev/null || xdg-open http://127.0.0.1:8080 2>/dev/null || true
  exit 0
fi
```

### 3. Start in background

The Maggy install lives at `<bootstrap-root>/maggy`. Resolve it from `~/.claude/.bootstrap-dir`:

```bash
BOOTSTRAP_DIR=$(cat ~/.claude/.bootstrap-dir 2>/dev/null || echo "")
MAGGY_DIR="$BOOTSTRAP_DIR/maggy"

if [ ! -d "$MAGGY_DIR" ]; then
  echo "Maggy not installed. Run: cd <claude-bootstrap>/maggy && ./install.sh"
  exit 1
fi

cd "$MAGGY_DIR"
nohup python3 -m src.main > ~/.maggy/maggy.log 2>&1 &
echo $! > ~/.maggy/maggy.pid
```

### 4. Wait for health check

```bash
for i in {1..15}; do
  if curl -sf http://127.0.0.1:8080/api/health >/dev/null 2>&1; then
    echo "✓ Maggy ready at http://127.0.0.1:8080"
    open http://127.0.0.1:8080 2>/dev/null || true
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
