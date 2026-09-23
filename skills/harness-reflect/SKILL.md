---
name: harness-reflect
description: >-
  Reflector/curator for the coding harness: mine recent trajectories and failures,
  distill incremental playbook bullets (ACE-style), dedupe by id, and archive noise.
  Use when the harness stop hook fires, the user asks to update the playbook, or
  after a failed verifier loop.
disable-model-invocation: true
---

# Harness Reflect

Incremental context engineering — **merge bullets, never rewrite the whole playbook**.

## Inputs

1. `.cursor/harness/playbook.md`
2. New/changed files in `.cursor/harness/trajectories/` and `.cursor/harness/failures/`
3. Optional: `.cursor/harness/proposals/rejected.md` (do not repeat failed edits)

## Workflow

1. Read existing playbook bullets (`id:` + `desc:` lines).
2. Scan trajectories/failures since last reflect (use `.cursor/harness/state/last-reflect.json` if present).
3. Extract only **recurrent, verifier-grounded** insights:
   - same failure mechanism across sessions
   - stable repo facts (commands, paths, conventions)
   - user corrections that will apply again
4. **Curate** — for each candidate:
   - assign a stable `id` (kebab-case)
   - one-line `desc`
   - update in place if `id` exists, else append under `## Bullets`
5. Cap playbook at **24 bullets**; move dropped bullets to `.cursor/harness/archive/playbook-YYYY-MM-DD.md` with reason.
6. Write `.cursor/harness/state/last-reflect.json` with `{ "at": "<iso>", "files_processed": [...] }`.
7. If nothing qualifies, respond exactly: `No playbook updates.`

## Reject

- one-off task details, secrets, transient errors
- task-specific difficulty with no harness fix
- bullets that duplicate `AGENTS.md` or user rules — link instead

## Output format in playbook

```markdown
# Harness Playbook

## Bullets

- id: verify-before-done
  desc: Run the smallest verifier from config.json before claiming done.

- id: example-id
  desc: One line, actionable, no prose paragraphs.
```
