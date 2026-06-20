# Python idioms — judgment layer

The linter (`ruff --select C4,SIM,PERF,B,RUF,PIE`) catches the mechanical cases. This rubric is for the structural recognitions a linter misses — where the code works but a Python developer would write it differently. CLAUDE.md conventions override anything here.

## Reach for the stdlib before hand-rolling

- A loop that counts occurrences into a dict → `collections.Counter`.
- A dict whose values are appended-to lists/sets → `collections.defaultdict(list)`.
- A manual `lru`/memo dict on a pure function → `functools.lru_cache` / `functools.cache`.
- Manual cache of an expensive instance property → `functools.cached_property`.
- Nested loops over the product of two sequences → `itertools.product`.
- A running accumulation / flatten of nested iterables → `itertools.chain.from_iterable`, `itertools.accumulate`.
- Sorting then grouping adjacent equal keys → `itertools.groupby` (sort first).
- Sliding-window pairs → `itertools.pairwise`.
- A fixed-size FIFO/LIFO with `list.pop(0)` → `collections.deque`.

## Loops that aren't loops

- Building a list/set/dict by appending in a `for` → comprehension. Use a generator expression when the result is only iterated once (streaming, `sum()`, `any()`, `max()`).
- `for i in range(len(xs))` → `enumerate(xs)`; two parallel sequences → `zip`.
- `sum`/`min`/`max`/`any`/`all` over a hand-written accumulator loop.

## Structured data

- Parallel lists or dicts-of-fixed-keys passed around together → a `@dataclass` (or `typing.NamedTuple` for immutable). Bare tuples indexed by position (`row[3]`) are a smell.
- Returning a multi-field dict that callers index by string key → a dataclass with typed fields.

## Control flow & access

- `if k in d: x = d[k] else: x = default` → `d.get(k, default)`; accumulate-into-key → `d.setdefault` / `defaultdict`.
- Nested `if` pyramids → early `return`/`continue` (guard clauses).
- LBYL existence checks around an operation that could just be tried → EAFP (`try/except`) where it reads cleaner.
- `len(x) == 0` / `len(x) > 0` → truthiness (`if not x` / `if x`).

## Resources, paths, strings

- Manual `open()`/`close()` or `try/finally` cleanup → `with` context managers; write your own with `contextlib.contextmanager` when a cleanup pair recurs.
- `os.path.join`/`os.path.exists` string-wrangling → `pathlib.Path`.
- `%`-formatting or `.format()` → f-strings.

## Traps

- Mutable default arguments (`def f(x=[])`) — flag always.
- Returning `None` vs raising for the same failure mode in different branches — pick one.
- Building large lists in memory that are consumed once — prefer a generator.
