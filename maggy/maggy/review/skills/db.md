# Review skill — DB / migrations (zenloop-db, Alembic / SQL)

Migrations are **append-only** and high-blast-radius — scrutinize hard.

## Blocking
- **Destructive ops** — `DROP TABLE`, `DROP COLUMN`, `ALTER COLUMN ... TYPE`,
  `TRUNCATE` — without an explicit ADR justifying them. Default-block; require a
  linked Accepted ADR (read it) before clearing.
- **`ADD COLUMN ... NOT NULL` without a `DEFAULT`/backfill** on a non-empty table
  → write failure / long lock. Require a default or a staged backfill.
- **One service's migration touching another's schema** (must be per-service:
  `surveys.*`, `email.*`, `ai.*`, `shared.*`).
- **Non-parameterized dynamic SQL** built from input.

## Scrutinize (flag with rationale)
- **`ON DELETE` action** on new FKs: is `CASCADE` vs `RESTRICT`/`SET NULL`
  justified? `CASCADE` on a parent can wipe large child trees (and cascade
  transitively — check the child's own FK delete action with `grep`). `SET NULL`
  needs the column nullable. The choice must be reasoned in the ADR.
- **`NOT VALID` FK pattern**: adding `NOT VALID` then deferring `VALIDATE` is the
  correct low-lock pattern when pre-existing rows would fail — confirm the ADR
  explains why VALIDATE is deferred.
- **Reversibility**: does `downgrade` exist and undo cleanly?
- **Index creation** on large tables should be `CONCURRENTLY` (outside a txn).
- **Migration numbering**: unique, sequential; no collision with an existing
  migration or **ADR** number (grep the registry — ADR/migration numbers are
  separate namespaces but both must be unique within their own).

## Verify
- Use `grep`/`read_file` against `zenloop-db` and the schema docs to confirm FK
  delete actions, existing migration numbers, and whether a referenced table/column
  actually exists — don't assert from the diff alone.
