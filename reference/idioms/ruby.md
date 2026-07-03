# Ruby idioms — judgment layer

The linter (`rubocop`) catches the mechanical cases. This rubric is for the structural recognitions a linter misses — where the code works but a Ruby developer would write it differently. CLAUDE.md conventions override anything here.

## Loops that aren't loops

- `for`/`each` building up an accumulator → `map`/`select`/`reject`/`reduce`.
- `n.times` building an array by pushing → `Array.new(n) { ... }` or `map`.
- Nested `each` flattening results by hand → `flat_map`.

## Blocks & symbols

- A `{ |x| x.method }` block that only calls one method on the element → `&:method` shorthand.
- `do...end` used for a value-returning one-liner, or `{}` used for a multi-line side-effecting block — swap to match the convention (`{}` for values, `do...end` for effects).

## Control flow

- `if/else` whose branches are only `true`/`false` → return the boolean expression itself.
- `unless` with an `else` branch → invert the condition and use `if`.
- Nested `if` pyramids → guard clauses with `return`/`next`.

## Structured data

- Hash access guarded by manual `nil` checks → `dig` or `fetch` with a default.
- Parallel arrays or hashes passed around together → a `Struct.new` or small class.
- More than three positional arguments → keyword arguments.

## Objects & methods

- Hand-written getter/setter methods with no extra logic → `attr_accessor`/`attr_reader`/`attr_writer`.
- Explicit `x == nil` / `nil == x` → `x.nil?`.
- `respond_to?` guarding a call that could just be made and rescued — prefer duck typing over pre-checking.

## Traps

- `rescue => e` (or a bare `rescue`) swallowing `StandardError` broadly enough to hide real bugs.
- Mutating a method argument in place (`arr.push!`-style side effects on a passed-in object) where a pure transform is expected.
- `define_method`/`method_missing` reached for where a handful of explicit methods would be clearer.
