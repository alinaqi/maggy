# Uninstalling

Reverting Claude Bootstrap / Maggy is meant to be safe and reversible. The
installer only *adds* managed files into standard locations — it never edits
your existing dotfiles in place (with one exception: srooter shell routing, if
you enabled it, adds one line to your shell rc).

## TL;DR

```bash
maggy uninstall          # dry-run — shows exactly what would be removed
maggy uninstall --yes    # actually remove the managed assets
pip uninstall maggy-harness
```

`maggy uninstall` is **dry-run by default** and only removes the asset *names*
the installer placed — your own files in `~/.claude`, `~/bin`, and `~/.maggy`
are left untouched.

---

## Backup, restore & diff (before you install)

You don't have to take Maggy's word for it — preview and snapshot first:

```bash
maggy diff               # what would change vs your current setup (+new / ~changed / identical)
maggy backup             # snapshot your existing files (settings.json + anything Maggy would overwrite)
maggy restore --list     # list snapshots
maggy restore            # restore the newest (or --id <stamp>)
```

`maggy bootstrap` **auto-backs-up first** — so your very first install captures
your pristine, pre-Maggy state. To roll the machine back to exactly how it was:

```bash
maggy restore            # bring back your original files
maggy uninstall --yes    # remove Maggy's added files
```

Backups live in `~/.maggy/backups/<timestamp>/` (a plain mirror of your home
layout — you can also just copy files back by hand). They capture **only** your
own pre-existing files that Maggy would overwrite, never Maggy's own assets
(those come off with `maggy uninstall`). Skip the auto-backup with
`maggy bootstrap --no-backup`.

---

## What `maggy uninstall` removes

It mirrors the installer, removing only what it placed:

| Location | What |
|----------|------|
| `~/.claude/skills/` | the bundled skill folders |
| `~/.claude/commands/` | the bundled slash-command files |
| `~/.claude/hooks/` | the bundled hook scripts |
| `~/.claude/rules/` | the bundled rule files |
| `~/.claude/templates/` | the bundled templates |
| `~/bin/` | the model-delegation wrappers (`qwen3`, `deepseek`, `kimi`, …) |
| `~/.maggy/plugins/` | the installed plugin folders |
| `~/.claude/.bootstrap-dir` | the install marker |

If you installed from a checkout that's since moved, point at it:
`maggy uninstall --source /path/to/checkout --yes`.

---

## What it intentionally leaves (remove manually if you want a clean slate)

These hold data or are shared with other tools, so the uninstaller won't delete
them automatically:

**1. The Python package**
```bash
pip uninstall maggy-harness          # or: pipx uninstall maggy-harness
```

**2. Maggy data + config** — local DBs, workspaces, settings:
```bash
rm -rf ~/.maggy                      # ⚠️ deletes Maggy's local data
rm -rf ~/.config/maggy               # if present
```

**3. `~/.claude/settings.json` hook lines** — the installer doesn't own this
file, but `/initialize-project` or srooter may have wired hooks into it. After
removing the hook scripts, open it and delete any `hooks` entries that point at
`~/.claude/hooks/...` paths that no longer exist, so Claude Code doesn't warn.

**4. srooter shell routing** (only if you ran `srooterctl enable`):
```bash
srooterctl disable                   # stop routing new terminals
# then remove this line from ~/.zshrc if present:
#   [ -f "$HOME/.srooter/active.env" ] && . "$HOME/.srooter/active.env"  # srooter
rm -rf ~/.srooter                    # optional: drop the saved key + state
```

**5. Other tool configs the installer may have seeded** (safe to leave):
```bash
rm -f  ~/.kimi/config.toml.bootstrap
rm -f  ~/.codex/templates/AGENTS.md
rm -rf ~/.polyphony                  # if you used Polyphony
```

---

## Fully manual fallback (no `maggy` command available)

If the package is already gone and you just want the files out:

```bash
# managed asset dirs under ~/.claude (these are the bundled ones)
rm -rf ~/.claude/skills ~/.claude/rules ~/.claude/templates
rm -f  ~/.claude/.bootstrap-dir
# remove the bundled commands/hooks/bin wrappers by name as needed, then:
pip uninstall maggy-harness
```

> Tip: run `maggy uninstall` (dry-run) **before** `pip uninstall` to get the
> exact list of files for your install.
