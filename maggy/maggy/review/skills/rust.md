# Review skill — Rust

## Anti-patterns — flag on sight
- `.unwrap()` / `.expect()` on a fallible path that can run in production → propagate with `?` or handle (BLOCKING in library/server code).
- `panic!`/`unreachable!`/`todo!` left on a reachable path (BLOCKING).
- `unsafe` blocks without a `// SAFETY:` justification, or that break aliasing/lifetime invariants (BLOCKING — scrutinize hard).
- `.clone()` to silence the borrow checker where a borrow would do (perf/intent smell).
- Blocking calls (`std::fs`, `std::net`, `thread::sleep`) inside an async task → use the async runtime equivalents.
- `.lock().unwrap()` holding a `MutexGuard` across an `.await` (deadlock risk).

## Correctness & ownership
- Integer overflow in arithmetic on untrusted input → `checked_*`/`saturating_*` (overflow panics in debug, wraps in release).
- `as` casts that truncate/sign-flip silently → `try_into()`.
- Error types: a real `enum` error or `anyhow`/`thiserror`, not `Box<dyn Error>` everywhere losing context.
- Lifetimes that leak implementation; `'static` bounds added just to compile.
- `Drop` order / RAII assumptions; resources released on every path (incl. early `?`).

## Idioms
- Prefer iterators/combinators over manual index loops; `if let`/`match` exhaustiveness.
- Make illegal states unrepresentable (newtypes, enums) rather than runtime checks.

## Tests
- `#[test]` for new behavior incl. the `Err` arms; `#[should_panic]` only for genuine invariants.
- Run with the same features the change touches; doctests compile.
