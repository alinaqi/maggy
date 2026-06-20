# Review skill — C# / .NET

## Anti-patterns — flag on sight
- `async void` (except event handlers) → `async Task`; exceptions are otherwise unobservable (BLOCKING).
- `.Result` / `.Wait()` / `.GetAwaiter().GetResult()` on async in a request path → deadlock/thread-starvation (BLOCKING).
- Missing `await` (fire-and-forget Task) where completion/errors matter.
- `IDisposable` not disposed — no `using` / `await using` (leak, BLOCKING).
- String-built SQL → parameterized commands / EF parameters (SQL injection, BLOCKING/security).
- Swallowed exceptions `catch {}`; catching `Exception` then continuing silently.
- `DateTime.Now` for timestamps/storage → `DateTime.UtcNow`/`DateTimeOffset`.

## Correctness & async
- `CancellationToken` threaded through async APIs and honored.
- `ConfigureAwait(false)` in library code; no `.Result` reentrancy.
- Nullable reference types respected — no `!` null-forgiving to silence a real null.
- LINQ that enumerates a query multiple times or hides N+1 DB round-trips.
- `==` vs `.Equals` for value semantics; struct mutation copies.

## Idioms
- Dependency injection via constructor; `IOptions<T>` for config, not static reads.
- `record`/immutability for DTOs; expression-bodied where it reads clearer.

## Tests
- xUnit/NUnit tests for new behavior incl. async exception + cancellation paths.
- Cover the failure branches; don't assert only on mock interactions.
