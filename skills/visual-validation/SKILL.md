# Visual Validation — Autonomous Screenshot Verification

## Philosophy

Every UI change should be visually verified before it ships. Peekaboo captures pixel-accurate screenshots. The system compares before/after and flags visual regressions. No manual "looks good to me" — the machine verifies what the machine built.

## Autonomous Flow

```
static/* files modified (detected by auto-review-hook or E2E testkit)
    ↓
peekaboo image --mode screen → ~/.maggy/visual-verify/after-{ts}.png
    ↓
Compare with latest baseline (previous after-*.png)
    ↓
AI evaluation: Gemini Flash analyzes screenshot for visual regressions
    ↓
Report: CLEAN or REGRESSION_DETECTED with specific issues
```

## Quick Commands

```bash
# Install
brew install steipete/tap/peekaboo

# Capture full system screenshot
peekaboo image --mode screen --retina --path /tmp/screen.png

# Capture specific window
peekaboo image --mode window --app "Google Chrome" --path /tmp/window.png

# Verify Maggy dashboard after code change
peekaboo image --mode window --app "Google Chrome" --path ~/.maggy/visual-verify/after-$(date -u +%Y%m%d-%H%M%S).png

# Compare two screenshots
ls -la ~/.maggy/visual-verify/after-*.png  # review before/after pairs
```

## Autonomous Verification Flow (Claude Code)

```bash
# After making any static/ file change, Claude should:
1. git add maggy/maggy/static/ && git diff --stat HEAD  # check what changed
2. Restart Maggy: lsof -ti :8080 | xargs kill && python3 -m maggy.main &
3. Wait for health: curl -s http://localhost:8080/api/health
4. Capture screenshot: peekaboo image --mode screen --path ~/.maggy/visual-verify/after-$(date -u +%Y%m%d-%H%M%S).png
5. Compare with latest baseline in ~/.maggy/visual-verify/
6. AI evaluation: ~/bin/gemini-api --flash "Analyze this screenshot for visual regressions"
7. Report findings
```

## Maggy Dashboard Verification

```bash
# One-shot verification
curl -s http://localhost:8080/api/health && \
peekaboo image --mode screen --path ~/.maggy/visual-verify/verify.png && \
echo "✓ Dashboard verified — screenshot at ~/.maggy/visual-verify/verify.png"
```

## Integration Points

### Auto-Review Hook (already wired)
- Detects `static/` changes in git diff
- Auto-captures Peekaboo screenshot
- Saves before/after pairs in `~/.maggy/visual-verify/`

### E2E Testkit Plugin
- Visual regression testing as part of `POST /api/testkit/run`
- Compares screenshots against baselines
- Flags pixel differences above threshold

### Build-in-Public Plugin
- Peekaboo screenshots replace AI-generated images
- Real product captures for LinkedIn/X posts

## When to Use

| Scenario | Command |
|----------|---------|
| After static/ change | `peekaboo image --mode screen --path ~/.maggy/visual-verify/after.png` |
| Before committing UI change | Run verification flow above |
| Reviewing dashboard | Screenshot + AI analysis |
| Build-in-public post | Auto-captured by plugin |
| Cross-browser check | `peekaboo image --mode window --app "Safari"` |
