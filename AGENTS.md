# AGENTS.md — Rules for Coding Agents Working on This Repository

## What this repository is

ATURB core (`aturb/`) is CAD-neutral and language-neutral.

Everything specific to one CAD system lives in `packs/<name>/`.

Read `docs/ARCHITECTURE.md` before changing structure.

## Commands

- Sync environment: `uv sync`
- Tests without CAD: `uv run pytest -m "not freecad" -q`
- All tests (needs FreeCAD): `uv run pytest -q`
- Lint: `uv run ruff check .`
- File size limit: `uv run python tools/size_limit.py`
- Agnosticism lint: `uv run python tools/agnostic_lint.py`

## Hard rules

1. Do only the assigned task. List files before editing.
2. Never add an operations layer: no agent-callable create_box, fillet or hole functions.
3. Never add an intermediate geometry language, JSON geometry schema or DSL.
4. Never add multi-agent logic, background summarizers or design graphs.
5. Never put a CAD brand name or CAD concept inside `aturb/`.
6. Pack helpers may select, measure and assert. They may never create features.
7. Never guess a library API. Verify with a tiny command first. Use only calls recorded in `docs/api_notes/` or verified in-session.
8. Files at most 300 lines. Changes at most ~200 lines per task.
9. No absolute paths or machine-specific values in committed files. Use config.
10. Mark every chosen default with `# starting default`.
11. Do not commit. Report `git status --short` and acceptance output.

## Layout

- `aturb/` — core service (CAD-neutral)
- `packs/` — backend packs: FreeCAD, stub
- `clients/` — thin clients of the core service
- `projects/` — example CAD projects
- `evals/` — tasks, correct answers, results
- `tools/` — lints, limits, spikes
- `tests/` — pytest; FreeCAD tests marked `@pytest.mark.freecad`
- `docs/` — architecture, environment, ADRs, API notes