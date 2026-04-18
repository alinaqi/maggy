# /maggy-init — Set Up Maggy for This Team

Interactive wizard that configures Maggy for the user's org, issue tracker, and codebases. Writes `~/.maggy/config.yaml` and ensures deps are installed.

---

## Usage

`/maggy-init` — run the full setup wizard

---

## Steps

### 1. Check prerequisites

- Python 3.11+ available
- `claude` CLI on PATH (warn but don't block)
- claude-bootstrap installed (check `~/.claude/.bootstrap-dir`)

### 2. Run installer

```bash
BOOTSTRAP_DIR=$(cat ~/.claude/.bootstrap-dir)
cd "$BOOTSTRAP_DIR/maggy"
./install.sh
```

This installs Python deps and copies the config template to `~/.maggy/config.yaml`.

### 3. Interactive config wizard

Ask the user:

1. **Org name** — human-readable name (e.g. "Acme Corp")
2. **Domain** — primary competitive domain (e.g. "fintech", "devtools", "cx", "healthcare"). This drives competitor discovery.
3. **Issue tracker** — `github` (default) or `asana`. Linear is a stub.
4. **For GitHub:** org name + comma-separated repo list (`acmecorp/api, acmecorp/web`)
5. **For Asana:** workspace ID + project GID for their default board
6. **Codebases** — paths to each repo Maggy should execute in. Prompt key per path (short name like `api`, `web`).
7. **Competitor categories** — comma-separated (can match domain; encourages 1-3 categories)
8. **OKRs** — "skip" or "yaml" (paste OKRs inline if yaml)

### 4. Write config

Patch `~/.maggy/config.yaml` with the user's answers using a Python helper:

```python
import yaml
from pathlib import Path

cfg_path = Path.home() / ".maggy" / "config.yaml"
cfg = yaml.safe_load(cfg_path.read_text())

cfg["org"]["name"] = "<answer>"
cfg["org"]["domain"] = "<answer>"
cfg["issue_tracker"]["provider"] = "<answer>"
# ... set github/asana section accordingly
cfg["codebases"] = [{"path": "<path>", "key": "<key>"}, ...]
cfg["competitors"]["categories"] = ["<cat>", ...]

cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
```

### 5. Credentials check

Tell the user to export these in their shell and source them when starting Maggy:

```
export GITHUB_TOKEN=ghp_...           # repo + issues scopes
export ANTHROPIC_API_KEY=sk-ant-...
```

**Do not write tokens to `~/.maggy/.env`** — the Maggy server does not load that
file automatically, so credentials would sit on disk in plaintext with no code
reading them. Use your shell's standard secret store (e.g. `.zshrc`, `direnv`,
`op run`, a secrets manager) or export them inline when launching Maggy.

### 6. Test the connection

```bash
cd "$BOOTSTRAP_DIR/maggy"
python3 -c "from src import config, providers; cfg = config.load(); p = providers.build(cfg); import asyncio; print('Found', len(asyncio.run(p.list_tasks(limit=5))), 'tasks')"
```

If this returns tasks, setup is working.

### 7. Offer to launch

> Maggy is configured. Run `/maggy` to launch the dashboard, or:
>
> ```
> cd $BOOTSTRAP_DIR/maggy && python3 -m src.main
> ```
>
> Then open http://127.0.0.1:8080

---

## Related

- `/maggy` — launch dashboard
- `/icpg-bootstrap` — index your codebases so Execute gets rich context
