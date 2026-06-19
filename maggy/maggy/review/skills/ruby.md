# Review skill — Ruby / Rails

## Anti-patterns — flag on sight
- String-interpolated SQL in `where`/`find_by_sql` → parameterized (`where("x = ?", v)`) (SQL injection, BLOCKING/security).
- Mass-assignment without strong params; trusting `params` directly into `update`/`create` (BLOCKING).
- N+1 queries: association accessed in a loop without `includes`/`preload`.
- `rescue => e` that swallows or `rescue nil`; rescuing `Exception` (catches signals).
- Callbacks with side effects (emails, external calls) that make the model untestable / fire on every save.
- `save` without checking the return / `save!` where a soft failure is expected (and vice-versa).
- Time without zone (`Time.now`) → `Time.current`/`Time.zone.now`.

## Correctness
- `nil` handling: `&.` where a chain can be nil; `present?`/`blank?` vs truthiness.
- Money as float (BLOCKING) → integer cents / `BigDecimal`.
- Authorization checked per action (scoped to current_user/tenant), not just authentication.
- Strong-params permit lists match what the action actually needs (no over-permit).

## Idioms
- Skinny controllers, logic in services/POROs; query objects over fat scopes.
- Guard clauses over nested conditionals; predicate methods end in `?`.

## Tests
- RSpec/Minitest for new behavior incl. validation + authorization failure paths.
- Avoid testing through mocks only; exercise the real object where cheap.
