# Rust idioms — judgment layer

The linter (`cargo clippy`) catches the mechanical cases. This rubric is for the structural recognitions a linter misses — where the code works but a Rust developer would write it differently. CLAUDE.md conventions override anything here.

## Ownership & borrowing

- `.clone()` reached for to dodge a borrow-checker error, rather than restructuring or borrowing.
- `&String`/`&Vec<T>` parameters where `&str`/`&[T]` would accept both owned and borrowed callers.
- Explicit lifetime annotations where lifetime elision would already compile.

## Iterators

- A `for` loop pushing into a `Vec` → `.collect()` over `map`/`filter`/`fold`.
- Manual index loops (`for i in 0..v.len()`) → `.iter().enumerate()` or `.zip()`.
- A chain of `.unwrap()` after `.find()`/`.filter()` where `.and_then()`/`.ok_or()` reads cleaner and stays lazy.

## Error handling

- `.unwrap()`/`.expect()` on a path that can fail at runtime, outside tests/prototypes → propagate with `?`.
- Stringly-typed errors (`Err("something failed".to_string())`) → `thiserror` for libraries, `anyhow` for applications, or a custom enum.
- `panic!` used for a condition the caller could recover from.

## Types & structure

- Boolean flags standing in for mutually exclusive states → an `enum` with the states as variants.
- `Option<Option<T>>` or deeply nested `Option`/`Result` → flatten with `?`, `.flatten()`, or `.and_then()`.
- A raw `String`/`u64` used as an ID or unit-bearing value across the codebase → a newtype wrapper.

## Traits & generics

- A generic bound (`fn f<T: Trait>(x: T)`) where the caller never needs to name `T` → `impl Trait` in argument position.
- Hand-written `Clone`/`Debug`/`PartialEq` where `#[derive(...)]` would produce the same semantics.

## Traps

- Repeated `.clone()` calls are a signal to reconsider ownership, not a fix to apply and move on.
- `match` arms that discard bound data with `_` where the caller likely needed it.
- A `Mutex`/`RwLock` guard held across an `.await` point — blocks the executor instead of just the critical section.
