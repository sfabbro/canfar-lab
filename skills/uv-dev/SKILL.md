---
name: uv-dev
description: >-
  uv Python workflow when pyproject.toml + uv.lock exist and there is no
  pixi.toml: sync, run, pytest, ruff. Use for OpenCADC, canfar-containers
  modules, and other uv.lock trees — not owned astroai/sfabbro science packages.
---

# uv dev workflow

## Detect

Repo uses uv when `pyproject.toml` and `uv.lock` exist and **no** `pixi.toml` /
`[tool.pixi]` at the project root.

Typical: **opencadc/canfar**, **deployments**, **canfar-containers** `ray/manager`,
third-party clones. Owned astroai/sfabbro **science packages** use **pixi-dev**.

## Setup profiles

| Use case | Command |
|----------|---------|
| Core | `uv sync` |
| Tests | `uv sync --extra test` or `uv sync --group dev` |
| Full | `uv sync --all-extras --dev` |

## Run

```bash
uv run pytest -q
uv run pytest tests/path/test_foo.py -q
uv run ruff check .
uv run python script.py
```

**Never** use bare `python` or `pip install` into `$HOME` when uv manages the project.

## Agent loop

1. Read `AGENTS.md` at repo root.
2. Use **harness-coding** for plan → execute → verify.
3. Run `uv run pytest` (or the repo’s documented CI script) before claiming done.
