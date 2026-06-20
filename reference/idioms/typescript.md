# TypeScript / JavaScript idioms — judgment layer

The linter (`eslint` with `eslint-plugin-unicorn`, or `biome check`) catches the mechanical cases. This rubric is for the structural recognitions a linter misses. CLAUDE.md conventions override anything here.

## Types

- `any` → `unknown` plus narrowing, or a precise type. `as` assertions that bypass the checker are a smell; prefer type guards.
- Boolean flags that are mutually exclusive or drive a shape change → a discriminated union (`{ kind: 'a'; ... } | { kind: 'b'; ... }`).
- A bag of optional fields where only some combinations are valid → model the valid states as a union, not one wide object.
- `as const` for literal tuples/objects; `readonly` for arrays/props that shouldn't mutate.
- A union of string literals usually beats an `enum`.

## Loops that aren't loops

- Building an array by `push` in a `for` → `map`/`filter`/`flatMap`/`reduce`.
- Existence/aggregate checks → `some`/`every`/`find`/`includes`, not a manual loop with a flag.
- `Object.keys/values/entries` + iteration over manual `for...in`.

## Access & control flow

- Nested null checks → optional chaining `?.` and nullish coalescing `??` (not `||`, which swallows `0`/`''`/`false`).
- Nested `if` pyramids → early return guard clauses.
- Destructuring for multi-field access and for default values, over repeated `obj.x` / `x = obj.x ?? d`.

## Data structures

- An object used as a keyed map with non-string keys, or that needs ordered iteration / frequent add-remove → `Map`. A set of unique values → `Set`.
- Spreading (`{...a, ...b}`, `[...xs, y]`) over `Object.assign`/`concat` for the common immutable cases.

## Async

- `async/await` over `.then()` chains; `Promise.all` for independent awaits instead of awaiting in sequence.
- Don't swallow rejections — every `await` that can throw is in a `try/catch` or has a deliberate boundary.

## Traps

- `==` where `===` is meant.
- `||` for defaulting when the value can legitimately be `0`/`''`/`false` → `??`.
- Mutating function arguments or shared state where a pure transform is clearer.
