# Review skill — TypeScript / React (frontend-app)

## FE-specific rules
1. **New features MUST be feature-flagged.** Any net-new user-facing feature
   (route, page, panel, drawer, widget) must be gated behind a flag —
   `useFeatureFlag('...')` or a `VITE_FF_*` env flag — so it is NOT shipped to all
   users by default. A new feature entry point with no flag gate is **BLOCKING**;
   cite the ungated mount/route `file:line`. (Bug fixes / changes to already-shipped
   features don't need a new flag.)
2. **i18n: both `de` AND `en`, German INFORMAL.** Every new user-facing string
   needs keys in BOTH the `en` and `de` locale files — no hardcoded literals in
   components. German MUST use **du/dein/deine**, never **Sie/Ihr/Ihre**. Use ICU
   `{count}`, never legacy `{{count}}`. Missing `de` key, hardcoded string, or
   formal German = **BLOCKING**. (Verify with `grep` against the locale JSON.)
3. **Follow FE guidelines** (`docs/`): Nx lib boundaries (no
   `@nx/enforce-module-boundaries` violations unless an explicit, justified
   `eslint-disable`), TypeScript strictness (no stray `any`), feature/lib layering,
   no secrets in client-exposed `VITE_*` / `NEXT_PUBLIC_*` / `REACT_APP_*`,
   accessible + i18n'd UI, and tests for new logic.

## Correctness
- `useEffect` deps, stale closures, missing cleanup; unbounded re-renders.
- `any`/unsafe casts hiding type errors; non-null `!` on possibly-undefined values.
- Async: unhandled promise rejections, race conditions on rapid state updates.
- Accessibility: interactive elements need roles/labels; keyboard support.

## Verify, don't assume
- To check a flag/translation/import, `grep` the locale JSON or the file — don't
  infer from the diff alone (a key may already exist in an unchanged file).
