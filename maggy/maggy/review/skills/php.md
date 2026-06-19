# Review skill — PHP / Laravel

## Anti-patterns — flag on sight
- Raw query with interpolated input → prepared statements / query-builder bindings (SQL injection, BLOCKING/security).
- Unescaped output in templates → `echo` of user data without `htmlspecialchars`/Blade `{{ }}` (XSS, BLOCKING).
- Mass assignment without `$fillable`/`$guarded`; `Model::create($request->all())` (BLOCKING).
- `@` error suppression; `catch (\Exception $e) {}` swallow; continuing after a failed operation.
- `==` loose comparison on auth/identity values → `===` (type-juggling auth bypass, BLOCKING/security).
- N+1: Eloquent relation accessed in a loop without eager `with()`.
- Secrets in code / committed `.env`; `env()` called outside config (cached config breaks it).

## Correctness
- Null/undefined array keys (`$a['k']` without `isset`/`??`); nullable returns handled.
- Money as float (BLOCKING) → integer minor units / a money library.
- Authorization (policies/gates) enforced per action, scoped to the current user/tenant.
- Validation at the boundary (Form Requests), not ad-hoc in controllers.
- Mixing business logic into controllers/models → services/actions.

## Idioms
- `declare(strict_types=1)`; typed properties + return types.
- Dependency injection via the container, not `new`/facades deep in logic.

## Tests
- PHPUnit/Pest tests for new behavior incl. validation + authorization failure paths.
- Don't cover new code only via HTTP mocks; assert real outcomes.
