# Go idioms — judgment layer

The linter (`golangci-lint run`) catches the mechanical cases. This rubric is for the structural recognitions a linter misses — where the code works but a Go developer would write it differently. CLAUDE.md conventions override anything here.

## Errors

- Returning an error without context → wrap it: `fmt.Errorf("doing x: %w", err)`.
- Comparing errors with `==` or string matching → `errors.Is`/`errors.As` against a sentinel or typed error.
- `_ = err` discarding an error with no comment explaining why it's safe to ignore.
- Ad-hoc error strings scattered across call sites → a package-level sentinel (`var ErrNotFound = errors.New(...)`) or typed error the caller can match on.

## Interfaces & structs

- A struct returned where only behavior is needed → accept interfaces, return concrete structs.
- Interfaces defined by the producer package "just in case" → define them at the point of use, kept to 1-2 methods.
- Getter/setter methods for exported fields with no invariant to protect — just export the field.

## Control flow

- Nested `if` pyramids → early `return`/`continue` guard clauses.
- `if/else if/else` chains keying off the same value → `switch`.
- Naked returns in a function longer than a few lines — name the outputs or return explicitly.

## Concurrency

- A goroutine started with no way to wait for it or cancel it (no `WaitGroup`, no `context`) — leak risk.
- Shared state mutated from more than one goroutine without a mutex or channel.
- `context.Context` stored in a struct field instead of threaded as the first parameter.

## Data & slices

- Repeated `append` growing a slice whose final size is known upfront → `make([]T, 0, n)`.
- A constructor required to produce a usable value when the zero value could do the job.
- `nil` vs empty slice used inconsistently for the same meaning — pick one and document it if it affects JSON output.

## Traps

- `defer` inside a loop — the deferred calls pile up until the function returns, not the loop iteration.
- Shadowing `err` in a nested scope (`if err := ...; err != nil`) that silently drops the outer error.
- `panic` for an error the caller could reasonably recover from — return an `error` instead.
