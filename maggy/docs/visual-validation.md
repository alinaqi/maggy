# Visual Validation

Functional tests prove the code *works*. Visual tests prove the UI *looks right* —
they catch the regressions unit tests can't see: a broken layout, a clashing
color (like the grey tab-bar band), an overflowing element, a button that
vanished. Visual validation is a first-class part of Maggy's test flow.

## The model: golden images

A visual test renders the real dashboard in a headless browser, screenshots a
view, and compares it pixel-by-pixel against a **golden** image checked into the
repo (`tests/visual/golden/<name>.png`).

- **Match** → test passes.
- **Mismatch** → test fails with a red-highlighted diff at
  `tests/visual/golden/<name>_diff.png` and the % of pixels that changed.
- **No golden yet** (first run) → a candidate is written and the test fails with
  a "review me" message. Accept it (below) and it becomes the golden.

An anti-aliasing tolerance (per-channel delta ≤ 12) absorbs sub-pixel font noise
so you don't get false diffs from harmless rendering jitter.

## Writing a visual test

Drop a test in `tests/visual/`. The `visual`, `page`, and `test_server`
fixtures are provided:

```python
def test_chat_tab_bar(visual, page, test_server):
    page.goto(test_server.url, wait_until="networkidle")
    page.evaluate("() => switchTab('chat')")
    page.wait_for_timeout(500)
    visual.snapshot("chat-tab-bar", full_page=False)      # whole viewport
    # or scope to one element:
    visual.snapshot_element("tab-bar-only", "#pane-chat .session-tabbar")
```

That's the whole API:

| Call | What it captures |
|------|------------------|
| `visual.snapshot(name)` | full page |
| `visual.snapshot(name, full_page=False)` | viewport only |
| `visual.snapshot_element(name, selector)` | one element |

## The workflow (runs naturally with `pytest`)

1. **Write the test** alongside your feature, just like a unit test.
2. **First run** writes a candidate and fails — open
   `tests/visual/golden/<name>_candidate.png` and confirm it looks right.
3. **Accept the golden:**
   ```bash
   MAGGY_UPDATE_GOLDENS=1 pytest tests/visual/      # writes goldens, passes
   ```
   (or just rename `<name>_candidate.png` → `<name>.png`).
4. **Commit the golden** — it's now the spec. Future runs compare against it.
5. **When you intentionally change the UI**, the test fails; review the diff,
   then re-accept with `MAGGY_UPDATE_GOLDENS=1`.

## Where it fits in the dev flow

- **Local**: `pytest tests/visual/` is part of the normal suite. It **auto-skips**
  when Playwright / the chromium binary aren't installed, so it never blocks a
  contributor who hasn't opted in.
- **Enable it**: `pip install maggy-harness[visual] && playwright install chromium`.
- **TDD loop**: write the visual test in the RED phase (it has no golden → fails),
  build the UI, accept the golden in the GREEN phase. The golden *is* the
  acceptance criterion — the same RED→GREEN rhythm as functional TDD.
- **CI**: run goldens on a pinned browser/OS so font rendering is stable; treat a
  visual diff like any other failing test (review the `_diff.png` artifact).

## Why golden images (not an LLM "does this look right?")

Deterministic, fast (numpy-vectorized diff, ~50ms/image), free, and reviewable in
a normal PR diff. An LLM check is non-deterministic and costs tokens on every
run; goldens give you a hard, reproducible gate. (An LLM *describing* a first-run
candidate is a fine optional add-on, but the gate itself stays pixel-exact.)
