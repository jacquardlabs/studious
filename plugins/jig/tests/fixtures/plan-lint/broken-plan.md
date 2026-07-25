# Plan: plan-lint broken fixture

Deliberately broken, per docs/design/plan-lint.md's "Required demonstration"
-- one distinct violation category per task, so a single `scripts/plan-lint`
run against this file demonstrates all eight in one pass. Not a real build
plan; never run through `/build`. Task 8 exists only to make Task 7
LOAD-BEARING (`Rests on: Task 7`) -- it is otherwise clean.

### Task 1 — cap-count: no [cap] item
Why now:    demonstrates cap-count.
Read first: `scripts/_gitutil.py`
Rests on:   n/a
Do:         nothing real -- fixture only.
Not here:   n/a

Done means:
1. [hold] first hold item    (tier: script `scripts/_gitutil.py`)
2. [hold] second hold item   (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- fixture only.

### Task 2 — hold-count: no [hold] item
Why now:    demonstrates hold-count.
Read first: `scripts/_gitutil.py`
Rests on:   n/a
Do:         nothing real -- fixture only.
Not here:   n/a

Done means:
1. [cap] first cap item    (tier: script `scripts/_gitutil.py`)
2. [cap] second cap item   (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- fixture only.

### Task 3 — item-count: more than 5 items
Why now:    demonstrates item-count.
Read first: `scripts/_gitutil.py`
Rests on:   n/a
Do:         nothing real -- fixture only.
Not here:   n/a

Done means:
1. [cap]  `c1` behavior    (tier: script `scripts/_gitutil.py`)
2. [cap]  `c2` behavior    (tier: script `scripts/_gitutil.py`)
3. [cap]  `c3` behavior    (tier: script `scripts/_gitutil.py`)
4. [hold] `h1` behavior    (tier: script `scripts/_gitutil.py`)
5. [hold] `h2` behavior    (tier: script `scripts/_gitutil.py`)
6. [hold] `h3` behavior    (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- fixture only.

### Task 4 — invalid-tier: the forbidden `judgment` token
Why now:    demonstrates invalid-tier.
Read first: `scripts/_gitutil.py`
Rests on:   n/a
Do:         nothing real -- fixture only.
Not here:   n/a

Done means:
1. [cap]  a call that reads right but was never mechanically checked   (tier: judgment)
2. [hold] fine item                                                    (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- fixture only.

### Task 5 — method-not-found: named method doesn't exist
Why now:    demonstrates method-not-found.
Read first: `scripts/_gitutil.py`
Rests on:   n/a
Do:         nothing real -- fixture only, and does NOT mention scripts/does-not-exist.py.
Not here:   n/a

Done means:
1. [cap]  running `scripts/does-not-exist.py` exits 0   (tier: script `scripts/does-not-exist.py`)
2. [hold] fine item                                      (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- fixture only.

### Task 6 — read-first-unresolved: pointer to a since-renamed file
Why now:    demonstrates read-first-unresolved.
Read first: `scripts/renamed-does-not-exist.py`
Rests on:   n/a
Do:         nothing real -- fixture only.
Not here:   n/a

Done means:
1. [cap]  `renamed` behavior still holds   (tier: script `scripts/_gitutil.py`)
2. [hold] fine item                        (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- fixture only.

### Task 7 — load-bearing-cap-vague: LOAD-BEARING cap with no concrete referent
Why now:    demonstrates load-bearing-cap-vague; Task 8 below rests on this one, making it LOAD-BEARING.
Read first: `scripts/_gitutil.py`
Rests on:   n/a
Do:         nothing real -- fixture only.
Not here:   n/a

Done means:
1. [cap]  behaves correctly when called, as expected   (tier: script `scripts/_gitutil.py`)
2. [hold] no regression                                (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- fixture only.

### Task 8 — clean; rests on Task 7 so it becomes LOAD-BEARING
Why now:    exists only to make Task 7 LOAD-BEARING.
Read first: `scripts/_gitutil.py`
Rests on:   Task 7
Do:         nothing real -- fixture only.
Not here:   n/a

Done means:
1. [cap]  `clean` item with a concrete referent   (tier: script `scripts/_gitutil.py`)
2. [hold] fine item                                (tier: script `scripts/_gitutil.py`)
Evidence: n/a -- fixture only.

## Not-here follow-ups
- A real, drafted follow-up about `scripts/_gitutil.py`'s CLI wiring.
- TODO
