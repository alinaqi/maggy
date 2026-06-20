# Review skill — Python (surveys-backend / zenEmail)

## Hard rules (a violation in surveys-backend = BLOCKING)
1. Routes never touch the DB — they call services.
2. Services never run raw SQL / import the DB driver — they call repositories.
3. Repositories are the only DB layer; one repo owns one schema.
4. No cross-service repository imports — cross-context reads go via HTTP (gateway)
   or a domain event, never `from other_service... import`.
5. Pydantic schemas at the HTTP boundary; internal types are dataclasses/domain models.
6. Per-service Alembic migrations — a migration only touches its own schema.
7. Auth0 JWT for end-users at the gateway; PASETO between services. Never share user tokens.

(zenEmail predates these — there, apply general best practices, not the layering rule.)

## Anti-patterns — flag on sight
- `datetime.utcnow()` / naive `datetime.now()` → `datetime.now(timezone.utc)` (BLOCKING).
- Pydantic v1: `.dict()`, `@validator`, `class Config:` → v2 `.model_dump()`,
  `@field_validator`, `model_config` (BLOCKING — CI greps for these).
- `os.getenv()` / `os.environ.get()` in `app/` → typed field on `Settings` (BLOCKING).
- `supabase.table(...)` / `from supabase` in a service (ADR-0006 removed it) (BLOCKING).
- `psycopg2` (ADR-0005 = psycopg3 only) (BLOCKING).
- `try/except Exception: pass` swallow → propagate or log + re-raise specific types.
- `print()` for logging → `logger.info("...: %s", v)`.
- Raw SQL string-built (SQL injection) → parameterized only (BLOCKING/security).
- Secrets/PII in logs (mask to last 4); secrets in code → `Settings` + env.

## Correctness & async
- Un-awaited coroutines, blocking calls in async paths, sync DB in async handlers.
- None/empty handling; treating a `datetime` as a `str` (e.g. `created_at[:10]`).
- `org_id` scoping on every authenticated route/query (authz is app-level, R-063).

## Tests (verify, don't assume)
- New behavior needs tests that exercise the change (not mock-only).
- Async tests: confirm `asyncio_mode = auto` in `pytest.ini`/`pyproject.toml`
  (read it) before claiming bare `async def` tests are no-ops.
- Cover failure paths and `org_id` boundaries; flag untested new code paths.

## Migrations touched from Python → also load the **db** skill rules.
