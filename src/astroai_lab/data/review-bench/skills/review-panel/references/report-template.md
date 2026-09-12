# Panel report — <YYYY-MM-DD>-<slug>

_Write this from `01-findings.json`, never from memory. The brief is `00-brief.md`._

## Verdict summary

| claim | verdict | label | one-line justification |
|---|---|---|---|
| C1 | survives / refuted | established / suggestive / speculative | `<the decisive test or the blocking finding>` |

## Findings

| id | persona | severity | claim | evidence pointer | attested? | status |
|---|---|---|---|---|---|---|
| S1 | statistician | BLOCKER | C1 | `<command → output>` / `file:line` | attested / UNVERIFIED / demoted | open / fixed / withdrawn |

## Per-claim detail

### C1 — `<claim>`

- What was checked (and by whom): `<summary>`
- What survived and what did not: `<evidence>`
- Replication: `<route used, result>` — required for `established`
- Dissent (verbatim, with the test that would settle it): `<text>`

## Checks that found nothing

The coverage ledger. Recorded so a later reader can see what the panel *did* look at.

- `<persona>: <check> → nothing found`

## Infrastructure events

`<child id / persona>: INFRA_ERROR <tool result>` — a round is incomplete if this list is non-empty.

## Open falsification tests

| claim | cheapest test that could still kill it | cost | owner |
|---|---|---|---|
| C1 | | | |

## Opportunities (phase 6, not evidence, cannot raise a label)

| lens | opportunity | expected information gain | cost |
|---|---|---|---|

## Smallest set of fixes that would raise the weakest label

1. `<fix> → <label change>`
