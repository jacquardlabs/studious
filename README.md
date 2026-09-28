# studious (retired)

Studious was a Claude Code plugin for delivery discipline: gates around each feature, a build loop, and periodic health reviews. It was retired in September 2026 after a measurement showed its build loop added cost and human stops without improving the code it shipped.

## What replaced it

| You want | Use |
|---|---|
| Review a change, a document, or a whole repository | [gauntlet](https://github.com/jacquardlabs/gauntlet) — `/gauntlet:review` |
| Simplify a change against its intent, or survey a repo for dead weight | [exorcist](https://github.com/jacquardlabs/exorcist) — `/exorcist:exorcise`, `/exorcist:seance` |
| Interview-driven design docs and human sign-off | [viva](https://github.com/jacquardlabs/viva) |

## Taking an issue to a PR

The sequence that won the measurement, run in Claude Code with gauntlet and exorcist installed:

1. Paste the issue and ask Claude to implement it on a new branch, run the tests, and commit.
2. `/gauntlet:review`
3. "Fix the findings you judge real, re-run the tests, and commit. List any you judged not real, with why."
4. `/exorcist:exorcise <the issue>`
5. Push and open the PR.

One issue per branch and PR.

## Why

On 5 issues from two outside repos, bare Claude Code running the sequence above shipped 4 real defects. Studious's small mode shipped 21 at the same cost, because it recorded non-critical review findings instead of fixing them. The full record is in [#440](https://github.com/jacquardlabs/studious/issues/440). The code is in this repository's history; the last release is v6.13.1.
