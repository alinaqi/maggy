# Visual Validation with Peekaboo

Capture, analyze, and validate UI changes with pixel-accurate screenshots.

## Install

```bash
brew install steipete/tap/peekaboo
# Requires macOS Screen Recording + Accessibility permissions
```

## Quick Usage

```bash
# Capture full screen at Retina scale
peekaboo image --mode screen --retina --path ~/Desktop/screenshot.png

# Capture specific window
peekaboo image --mode window --app "Google Chrome" --path ~/Desktop/window.png

# Capture menu bar only
peekaboo image --mode menu --path ~/Desktop/menu.png
```

## Validate After Every UI Change

```bash
# Before change
peekaboo image --mode window --app "Google Chrome" --path /tmp/before.png

# Make changes...

# After change
peekaboo image --mode window --app "Google Chrome" --path /tmp/after.png

# Compare
open /tmp/before.png /tmp/after.png
```

## Integration with Maggy Dashboard

```bash
# Restart Maggy
lsof -ti :8080 | xargs kill; cd maggy && python3 -m maggy.main &

# Wait for startup
sleep 20 && curl http://localhost:8080/api/health

# Capture dashboard
peekaboo image --mode window --app "Google Chrome" --retina --path ~/Desktop/maggy-dashboard.png
```

## Integration with Build-in-Public

Replace AI-generated images with real screenshots:

```bash
# Capture hero screenshot for LinkedIn post
peekaboo image --mode window --app "Google Chrome" --path ~/.maggy/build-in-public/screenshots/hero-$(date +%Y%m%d-%H%M%S).png
```

## MCP Server (Claude Code Integration)

```bash
npx -y @steipete/peekaboo
# Available as MCP tool in Claude Code sessions
```
