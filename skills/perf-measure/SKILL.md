---
name: perf-measure
description: >-
  Measure performance with fair local evidence (hyperfine, timers, profiles)
  before and after a change. Use when optimizing, claiming speedups, debugging
  slow paths, or comparing kernels / I/O / UI responsiveness.
---

# Perf measure

No speed claim without same-machine baseline and treatment.

## Method

1. Restate the claim: workload, metric, threshold (e.g. p50 wall time ≤ X ms).
2. Fix the environment: same machine, data, warmup, thread/GPU state.
3. Prefer `hyperfine` for CLI/commands; otherwise a tight timer around the hot path.
4. Capture baseline (parent / old impl) and treatment (new) with the same command.
5. Report median ± spread, not a single lucky run. Note n and warmup.
6. If the win is numerical, also run `science-correctness` — faster wrong is worse.

## Tools (already local)

- `hyperfine 'cmd A' 'cmd B'`
- `verify-this` for VERIFIED / NOT VERIFIED / INCONCLUSIVE
- `control-ui` for UI/CDP perf profiles when the surface is a web/IDE UI
- repo CI tasks via `pixi-dev` / `uv-dev` when they already benchmark

## Anti-patterns

- Comparing cold vs warm runs as a “speedup”
- Changing input size between baseline and treatment
- Optimizing before a profiler or timer points at the hot path
