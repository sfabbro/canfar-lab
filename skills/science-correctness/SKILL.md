---
name: science-correctness
description: >-
  Always check math correctness, code logic, and physics before accepting
  numerical or scientific results. Use for astronomy/physics/ML numerics,
  coordinate transforms, units, WCS, statistics, loss functions, and any
  claim that depends on equations or invariants.
---

# Science correctness

Treat equations and physical claims as untrusted until checked. Prefer a
failing counterexample over a plausible explanation.

## When to use

- Any change touching math, units, coordinates, statistics, optics, orbits,
  photometry, cosmology, tensors, or numerical algorithms
- Reviewing agent output that quotes formulas, magnitudes, angles, or rates
- Performance work that changes numerics (fused kernels, approximations)

## Checklist (run in order)

1. **Restate the claim** in one falsifiable sentence (quantity, units, domain).
2. **Units / dimensions** — every term must match; convert before compare.
3. **Limits / invariants** — check known limits (flat sky, small angle,
   isotropic, zero flux, identity transform, conservation).
4. **Sign / handedness / conventions** — RA/Dec vs lon/lat, CD vs PC,
   radians vs degrees, column-major vs row-major, dtype/device.
5. **Independence check** — recompute with a second path (analytic limit,
   sympy/numpy reference, torch vs numpy, known catalog value).
6. **Edge cases** — empty input, NaN/Inf, wrap at 0/360, poles, singular WCS.
7. **Logic** — off-by-one, wrong broadcast, mask inverted, reduce axis wrong.

## Minimum evidence

Leave one runnable check that fails if the math is wrong:

- assert on a known identity or catalog value, or
- a 5–20 line script comparing two independent implementations

Do not call it done from “looks right” plots alone.

## Pair with

- `verify-this` — baseline vs treatment with a metric
- `pixi-dev` / `torchsky-dev` — repo-native runners
- `matplotlib-data-visualization` — honest plots after the numbers check out
- `orx-figures` — paper-size vector figures on OpenResearch sessions only (`orx install-skills`); do not vendor the orx skill tree here
