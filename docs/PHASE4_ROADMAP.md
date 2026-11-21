# Phase 4 task roadmap — task set and scoring

Draft task cards for Phase 4, derived from the Phase 3 roadmap
([`docs/PHASE3_ROADMAP.md`](PHASE3_ROADMAP.md)), the architecture
([`docs/ARCHITECTURE.md`](ARCHITECTURE.md)) and the runner contract
([`docs/adr/0004-runner-contract.md`](adr/0004-runner-contract.md)). The
orchestrator's Part 2 guide stays authoritative if it differs from this draft.

Scope: a task set and a scoring rule. A task is a folder with a task file, an
answer file and its own project. The runner builds the part named by the task
and scores it with the neutral checks of Phase 3. Phase 5 (the stock-agent
baseline) is out of scope here.

## Where this roadmap lives

`docs/` holds the architecture, the decision records and the phase roadmaps, and
the implementation guide Part 2 (Phases 3–4) is not in this repository yet. The
roadmap is therefore split in two, both next to
[`docs/PHASE3_ROADMAP.md`](PHASE3_ROADMAP.md):

- [`docs/PHASE4_ROADMAP.md`](PHASE4_ROADMAP.md) — this file: scope, decisions,
  schemas and dependencies.
- [`docs/PHASE4_TASKS.md`](PHASE4_TASKS.md) — the task cards T4.01 to T4.11.

## Scope boundaries (locked for Phase 4)

- No agent and no planning loop. Phase 4 scores the candidate part file that
  is already in the task's project. The stock-agent baseline is Phase 5.
- No runner contract change. [`BuildRequest`](../aturb/contract/types.py:26),
  [`BuildResult`](../aturb/contract/types.py:58),
  [`PackInfo`](../aturb/contract/types.py:113) and
  [`Runner`](../aturb/contract/runner.py:10) stay as they are, the contract
  version is not bumped and no failure kind is added.
- The answer schema stays at five keys. A sixth key needs a decision record and
  is out of scope here.
- No geometry DSL, no JSON geometry schema and no operations layer.
- No Phase 5 work: no model call, no pack prompt file, no retry loop, no
  parsing of agent output.

## Decisions

### D1 — A task ID and a part ID are two different things

A task is identified by its task ID. A task builds one part, identified by its
part ID. The two may differ, and the first task of the set already proves it:
task `plate_2holes` builds part `plt0001`. The task file therefore carries an
explicit `part_id`:

```toml
task_id = "plate_2holes"
part_id = "plt0001"
name = "Plate with two through holes"
description = "Build a 120 x 60 x 5 mm plate with two 10 mm through holes at x = -40 and x = +40."
```

- `task_id` must equal the name of the task folder. The folder is the identity
  of the task; the file repeats it so a reader of the file sees it.
- `part_id` is the part the task builds. It is never derived from the task ID.
- `part_id` must be a plain token: letters, digits, `_` and `-`, no path
  separator and no dot. It is the value that goes into the request.
- The task ID is never used as a part ID, and the part ID is never used as a
  task ID.
- `description` is a human-readable summary of the task for a reader. It is not
  the engineering prompt: the prompt lives in `project/requirements/` and is not
  a request field.

### D2 — `run_task()` builds the task's own project

```python
def run_task(task_dir: Path, runner: Runner, timeout_s: int) -> TaskResult:
    """Build and score one task folder."""
```

`task_dir` is the task folder. It holds `task.toml`, `answer.toml` and
`project/`. The build project is always `task_dir / "project"`.

There is no `project_root` parameter. The build project is derived from
`task_dir` and from nothing else: it is never passed in, never read from
`task.toml` and never taken from the working directory of the caller. The
request is built exactly like this:

```python
project = (task_dir / "project").resolve()
request = BuildRequest(
    project_root=str(project),
    part_id=spec.part_id,          # from task.toml, never the task ID
    language=runner.info().language,
    outputs=("native", "step"),
    timeout_s=timeout_s,
)
```

- `project_root` is the absolute path of `<task_dir>/project`.
- `part_id` comes from `task.toml` only.
- `language` comes from the runner's own `info().language`, never from the task
  file, so the core stays language-neutral.
- `outputs` is the contract default.
- `timeout_s` is passed in by the caller; the CLI reads it from the
  configuration, the way `aturb build` does.
- The runner is passed in, so `run_task()` loads no pack and reads no
  configuration.
- The engineering prompt is not a request field. The runner builds from the
  part file; the prompt is project input for the agent of Phase 5 and lives in
  `project/requirements/`.

### D3 — A malformed task is a result, not a skip

A task folder whose `task.toml` is missing or invalid is still a task of the
batch. It is never skipped and never counted as a pass.

- The fallback task ID is the task folder name.
- The result is an error result: `status = "error"`, `score = 0.0`,
  `part_id = ""` when the task file could not be read, and an error text that
  says what was wrong.
- The batch result list holds exactly one result per task folder, so the
  counts always add up.

## Layout of the task set

```text
evals/
  tasks/
    <task_id>/
      task.toml        # task_id, part_id, name, description
      answer.toml      # the correct answer: exactly five keys
      project/         # the build project of this task
        parts/         # the candidate part file
        expect/        # the expected values of the part
        requirements/  # plain-language engineering intent for the future agent
        out/           # runner-generated output
  results/
    <YYYY-MM-DD>_<HHMMSS>.toml   # one dated result file per run
```

The task's `project/` is an ordinary project folder with the same layout as
[`projects/demo`](../projects/demo): `parts/`, `expect/` and `requirements/`. It
holds the candidate part file that the runner builds, the expected values of the
part, and the plain-language engineering intent that the agent of Phase 5 will
read. `out/` is written by the runner and holds the build artifacts.

`expect/` is inside the candidate project, so its values are visible to the
candidate. `answer.toml` stays outside the candidate project, next to
`task.toml`, and the runner never reads it.

## The answer schema: five keys, fixed

```toml
task_id = "plate_2holes"
part_id = "plt0001"
expect_file = "expect/plt0001.toml"
required_checks = ["volume", "bbox_x", "bbox_y", "bbox_z", "hole_count"]
max_score = 1.0
```

- `expect_file` is relative to the task's build project.
- The expectation file always holds all five expected values — `volume`,
  `bbox`, `hole_count`, `hole_diameter` and `hole_positions` — even when
  `required_checks` names only a subset of the checks. A file with a missing or
  unknown value is refused by
  [`load_expectations()`](../aturb/verify/expectations.py:39).
- `required_checks` names the neutral checks that must pass. The names are the
  ones [`checks_from_expectations()`](../aturb/verify/expectations.py:57)
  produces: `volume`, `bbox_x`, `bbox_y`, `bbox_z`, `hole_count`,
  `hole_<n>_diameter`, `hole_<n>_x`, `hole_<n>_y`.
- `max_score` is the score a fully correct answer earns.
- The schema is exactly these five keys. Phase 4 adds no sixth key.

## The result record

The result record is written by the runner, not by the task author, so it is
not the answer schema:

```toml
[[results]]
task_id = "plate_2holes"
part_id = "plt0001"
status = "ok"
score = 1.0
error = ""
```

`status` is `ok`, `failed` or `error`.

## Dependency order

T4.01 → T4.02 → T4.03 → T4.04 → T4.05 → T4.06 → T4.07 → T4.08 → T4.09 →
T4.10 → T4.11

T4.04 may run in parallel with T4.03. Every other card waits for the card
before it. The cards are in [`docs/PHASE4_TASKS.md`](PHASE4_TASKS.md).

## Not in Phase 4

- An agent, a model call, a pack prompt file or a planning loop.
- A change to the runner contract, a new failure kind or a version bump.
- A sixth answer key, a geometry field, a geometry DSL or an operations layer.
- A second task, a task generator, a task index or a leaderboard.
- Anything from Phase 5.
