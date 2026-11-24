# /route-eval — Evaluate a project and set its routing profile

Analyze the current project's structure **and** your past routing history, then
recommend a per-project routing profile — e.g. a small, low-risk project can send
everything through one cheap model (like `glm-5.2`), while security-sensitive files
always escalate to Claude.

The profile is stored **privately, per-machine** at
`~/.claude/projects/<encoded-cwd>/routing.yaml` (never committed) and overrides the
global `~/.maggy/routing.yaml` for work in this project. It stays fully hand-editable.

---

## Usage

`/route-eval` — evaluate + show a recommendation, write only after you confirm
`/route-eval show` — print the project's current profile (if any)
`/route-eval --model <id>` — use a different cheap default for the `simple` profile

---

## Steps

Resolve the Maggy package from the bootstrap pointer and evaluate:

```bash
BOOTSTRAP_DIR="$(cat ~/.claude/.bootstrap-dir)"
RUN="PYTHONPATH=$BOOTSTRAP_DIR/maggy python3 -m maggy.route_eval"
```

### 1. Evaluate + recommend (default; never writes)

```bash
eval "$RUN plan --cwd \"$(pwd)\" --model glm-5.2"
```

Present the JSON to the user in plain language:
- **profile** — `simple` (one cheap model), `balanced` (complexity ladder), or
  `critical` (security surface / large repo → premium tiers).
- **default_model** — the model everything routes to under `simple`.
- **escalate_paths** — globs that always jump to Claude (auth/payments/billing).
- **_meta.evidence** — *why* this profile: file count, languages, security surface,
  and the dominant tier in your routing history.

Explain the trade-off in one line (cost vs. safety), then ask: **write this profile?**

### 2. Write it (only on explicit confirmation)

```bash
eval "$RUN apply --cwd \"$(pwd)\" --model glm-5.2"
```

Report the written path and remind the user it is private (not committed) and can be
edited by hand — profile, default model, and escalation rules are all adjustable.

### 3. Show the current profile

```bash
cat "$HOME/.claude/projects/$(pwd | tr '/' '-')/routing.yaml" 2>/dev/null \
  || echo "No profile yet — run /route-eval to create one."
```

---

## How it routes (once a profile exists)

The profile records the project's intent: `profile` (`simple` / `balanced` /
`critical`), the `default` model and the `escalate` rules (security, complexity,
`paths` globs). Model selection at task time comes from the harness profile tiers.

## Adjusting

Edit `~/.claude/projects/<encoded-cwd>/routing.yaml` directly. Common tweaks:
- Change `default.model` / `default.provider` to any model you have configured.
- Add your own `providers:` entry (model, `api_key_env`, `base_url`) to register a
  new backend — GLM, a local endpoint, anything.
- Add `escalate.paths` globs to force specific areas up to a stronger model.
- Flip `profile:` to `balanced`/`critical` to re-enable the full ladder.

---

## Notes

- **Nothing is committed** — the profile is per-machine under `~/.claude/projects/`.
- **Re-run anytime** — as the project grows, `/route-eval` re-reads the current
  structure + history and proposes an updated profile (still confirm-before-write).
- **History source** — `~/.claude/routing-log.jsonl` (tier distribution) informs the
  recommendation; a Claude/Codex-heavy history nudges away from `simple`.
- **Actually running a model** (e.g. GLM 5.2) still needs that provider wired as a
  `~/bin` wrapper or a `providers:` `base_url`; the profile decides *which* model,
  the provider layer executes it.
