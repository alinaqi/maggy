# Review skill — Go

## Anti-patterns — flag on sight
- Ignored errors: `val, _ := f()` where the error matters, or a bare `f()` that returns an error (BLOCKING).
- `err` checked but the underlying value used anyway after a non-nil error.
- Goroutine leaks: a goroutine with no exit path / unbuffered channel send with no receiver.
- `context.Context` not threaded through to blocking/IO calls; `context.Background()` deep in a call chain.
- Mutating a map/slice shared across goroutines without a mutex or channel (data race) (BLOCKING).
- `defer` inside a loop accumulating until function return (resource exhaustion).
- Naked `panic` in library code where an error return is expected.

## Correctness & concurrency
- `sync.WaitGroup` Add/Done balance; `Wait` actually reached on all paths.
- Channel close ownership (only the sender closes); no send on a closed channel.
- Slice aliasing: `append` reusing backing arrays causing surprise mutation.
- `nil` map writes (panic); `nil` interface vs typed-nil comparison bugs.
- Error wrapping with `%w` so callers can `errors.Is/As`; don't lose the chain.

## Idioms
- Return early; keep the happy path un-indented.
- Accept interfaces, return structs. Small interfaces at the consumer.
- No unused exported surface; lowercase what isn't part of the API.

## Tests
- Table-driven tests for new behavior; cover the error branches, not just happy path.
- `t.Parallel()` only where state is independent; race detector clean (`go test -race`).
