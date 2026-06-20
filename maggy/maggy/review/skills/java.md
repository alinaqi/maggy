# Review skill — Java

## Anti-patterns — flag on sight
- Swallowed exceptions: `catch (Exception e) {}` or catch-and-`printStackTrace` then continue (BLOCKING).
- Resources not closed: streams/connections/statements opened without try-with-resources (leak, BLOCKING).
- String concatenation building SQL → `PreparedStatement` with bind params (SQL injection, BLOCKING/security).
- `==` on objects (Strings, boxed numbers) where `.equals()` is meant.
- Returning `null` for a collection → return empty collection; `Optional` for maybe-absent scalars.
- Mutable static state / non-thread-safe singletons shared across threads.
- Catching `Throwable`/`Error`; swallowing `InterruptedException` without restoring the interrupt.

## Correctness & concurrency
- `equals`/`hashCode` overridden together and consistent; used as map keys safely.
- Unsynchronized access to shared mutable fields; check-then-act races → atomics/locks.
- Integer overflow / division; autoboxing NPEs (`Integer` unboxed when null).
- Stream pipelines with side effects or that consume a stream twice.
- Time/locale: `Instant`/`ZonedDateTime` over legacy `Date`; explicit `ZoneId`.

## Idioms
- Constructor injection over field injection; immutable objects/`final` where possible.
- Narrow visibility; no leaking internal mutable collections (defensive copies).

## Tests
- JUnit tests for new behavior incl. exception paths; no logic only covered by mocks.
- Assert on behavior/return, not implementation calls, where feasible.
