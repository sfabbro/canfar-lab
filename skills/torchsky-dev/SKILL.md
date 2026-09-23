---
name: torchsky-dev
description: >-
  Develop torchsky (torch-native astronomy stack) — pixi workflow, AGENTS.md
  conventions, WCS/sphere/catalogs patterns. Use in the torchsky repo or when
  editing torchsky-specific geometry, maps, or sphere code.
---

# torchsky-dev

Use when working in the **torchsky** repo (agents, CI, local installs).

## Interpreter and commands

1. **Pixi:** `pixi run preflight-push` before push (git hook). Targeted tests for files you changed. `pixi run ci-local` is optional local GitHub-suite parity, not a push blocker. Never rely on bare `python3` / `python` on PATH for project work.
2. Python **3.12+** supported (**`<3.15`**); see `pyproject.toml` `requires-python`.

## Install surfaces

- **Tests (pip):** `pip install -e ".[test]"` after installing `torch` (matches CI).
- **Bench + legacy comparators (pip):** `pip install -e ".[bench-all]"` after `torch`.
- **Pixi:** environments in `pixi.toml` (`test`, `bench-all`, `sphere-bench`, …).

See **AGENTS.md** at the torchsky repo root for the full policy.

## Boundaries

- FITS/table I/O lives in sibling **torchfits** — not in torchsky core.
- Heavy ecosystem packages (healpy, astropy, …) belong in test/bench extras, not default runtime imports.
