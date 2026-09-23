---
name: harness-improve
description: >-
  Self-harness loop: cluster failures into patterns, propose bounded edits to
  playbook/rules/skills, validate with held-in verifiers, log accept/reject. Use
  when coding quality plateaus, the same agent mistakes repeat, or the user asks
  to improve the harness itself.
disable-model-invocation: true
---

# Harness Improve

Self-Harness (weakness mining → bounded proposal → validation). The **evaluator sits outside** the edit: verifiers in `config.json` and CI must pass before merge.

## Editable surfaces (bounded)

| Surface | Scope |
|---------|--------|
| `.cursor/harness/playbook.md` | Bullets only |
| `.cursor/rules/harness-*.mdc` | Harness-specific rules |
| `.cursor/skills/*` | Project skills only |
| `.cursor/harness/config.json` | `verify` commands |

Do **not** edit application source, secrets, or unrelated rules without explicit user request.

## Stage 1 — Weakness mining

1. Read `.cursor/harness/failures/` and recent trajectories.
2. Cluster by **mechanism** (not surface error text): e.g. "skipped verifier", "wrong package manager", "context-only memory".
3. For each cluster, write `.cursor/harness/failures/pattern-<slug>.md`:

```markdown
# pattern <slug>
verifier_cause: <what failed>
mechanism: <agent behavior>
recurrence: <count or sessions>
addressable: yes|no
```

Skip clusters that are task difficulty, not harness-fixable.

## Stage 2 — Proposal

For each addressable cluster, draft **one narrow edit** in `.cursor/harness/proposals/<slug>.md`:

- target file + exact change
- bullets/rules to preserve (from passing sessions)
- distinct from `.cursor/harness/proposals/rejected.md`

Prefer playbook bullets over new rules.

## Stage 3 — Validation

1. Apply proposal to a scratch copy or branch.
2. Run all commands in `config.json` `verify` (held-in).
3. If a standard repo smoke exists, run it (held-out sanity).
4. **Accept** → merge edit, log line in `.cursor/harness/proposals/accepted.md`.
5. **Reject** → append to `rejected.md` with reason; do not change active harness.

Never accept a proposal that fixes one cluster but breaks verifiers.

## Automagic cadence

Run after `harness-reflect` when `failures/` has ≥3 files from the last 7 days, or when the user says "improve the harness".
