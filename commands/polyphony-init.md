# /polyphony-init — Setup Wizard

Initialize the Polyphony multi-agent orchestration environment.

---

## Steps

### 1. Check Prerequisites

```bash
command -v docker &>/dev/null || command -v orbctl &>/dev/null
```

If neither Docker nor OrbStack is available, inform the user:

> Docker or OrbStack is required for Polyphony container isolation. Install one first.

### 2. Create Config Directory

```bash
mkdir -p ~/.polyphony
```

### 3. Copy Config Templates

Copy default configuration files from the templates directory:

```bash
TEMPLATES="$(dirname "$(realpath "$0")")/../templates"
cp -n "$TEMPLATES/polyphony-config.yaml" ~/.polyphony/config.yaml
cp -n "$TEMPLATES/polyphony-identities.yaml" ~/.polyphony/identities.yaml
cp -n "$TEMPLATES/polyphony-agents.yaml" ~/.polyphony/agents.yaml
cp -n "$TEMPLATES/polyphony-routing.yaml" ~/.polyphony/routing.yaml
```

### 4. Build Worker Image

```bash
docker build -t polyphony-worker:latest -f templates/Dockerfile.polyphony .
```

### 5. Detect Available Agents

```bash
command -v claude &>/dev/null && echo "claude: available"
command -v codex &>/dev/null && echo "codex: available"
command -v kimi &>/dev/null && echo "kimi: available"
```

### 6. Confirm

Print summary of what was initialized and which agents are available.
