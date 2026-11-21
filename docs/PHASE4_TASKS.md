# Phase 4 task cards — task set and scoring

The task cards of Phase 4. The scope, the decisions and the schemas they
implement are in [`docs/PHASE4_ROADMAP.md`](PHASE4_ROADMAP.md); read that file
first. The orchestrator's Part 2 guide stays authoritative if it differs from
these cards.

Rules every card inherits:

- The core stays CAD-neutral: no CAD brand name or CAD concept inside `aturb/`.
- The runner contract does not change: no new field, no new failure kind, no
  version bump.
- Only calls recorded in the API notes or verified in-session may be used.
- Files at most 300 lines; each card changes at most about 200 lines.
- Every chosen default is marked `# starting default`.
- No commit; the orchestrator commits.

## T4.01 — Task set layout and the first task

GOAL: One task folder that shows the whole shape of the set: a task file, an answer file and its own project.

FILES (only these): `evals/tasks/plate_2holes/task.toml`, `evals/tasks/plate_2holes/answer.toml`,
`evals/tasks/plate_2holes/project/parts/plt0001_base_plate.py`,
`evals/tasks/plate_2holes/project/parts/plt0001_base_plate.stub`,
`evals/tasks/plate_2holes/project/expect/plt0001.toml`,
`evals/tasks/plate_2holes/project/requirements/plt0001.md`

DO EXACTLY:

1. Create the task folder with the six files above. The task ID is `plate_2holes` and the part ID is `plt0001`: the two differ on purpose.
2. `task.toml` holds `task_id`, `part_id`, `name` and `description`, as in D1 of the roadmap. The `description` is a human-readable summary, not the engineering prompt.
3. `answer.toml` holds the five keys of the answer schema, with `expect_file = "expect/plt0001.toml"` and the required checks `volume`, `bbox_x`, `bbox_y`, `bbox_z`, `hole_count`.
4. The part file is the demo plate: copy [`projects/demo/parts/plt0001_base_plate.py`](../projects/demo/parts/plt0001_base_plate.py) into the task project, and add a stub part file with the same part ID. Each runner discovers its own language-specific file: the FreeCAD pack looks for `parts/<part_id>_*.py` and the stub pack for `parts/<part_id>_*.stub`, so the same task runs under either pack.
5. The expectation file is the demo expectation: copy [`projects/demo/expect/plt0001.toml`](../projects/demo/expect/plt0001.toml) into the task project. It holds all five expected values, even though only some checks are required.
6. The requirements file holds the plain-language engineering intent for the part in one short paragraph: the plate size, the hole diameter and the hole positions. It is the prompt the agent of Phase 5 will read; Phase 4 never reads it.

DO NOT: change the demo project. Do not add a second task yet.

ACCEPTANCE: `task.toml` holds `task_id = "plate_2holes"` and `part_id = "plt0001"`; `answer.toml` holds exactly five keys; `git status --short` lists only the six new files.

DEPENDS ON: nothing.

## T4.02 — Task file loader and validation

GOAL: One loader that reads `task.toml` and refuses a task file that cannot be trusted.

FILES (only these): `aturb/evals/__init__.py`, `aturb/evals/task.py`, `tests/test_evals_task.py`

DO EXACTLY:

1. Create `aturb/evals/task.py` with a frozen dataclass `TaskSpec` (task_id, part_id, name, description) and a function `load_task(task_dir: Path) -> TaskSpec`.
2. The loader reads `<task_dir>/task.toml`. A missing file raises `FileNotFoundError`. A file that is not valid TOML, that misses a key, that holds an unknown key, that holds a value of the wrong type, whose `task_id` is not the folder name, or whose `part_id` is not a plain token raises `ValueError`.
3. The loader never guesses a part ID and never falls back to the task ID.
4. Create `tests/test_evals_task.py`: a valid task loads; a missing file, bad TOML, a missing key, an unknown key, a `task_id` that differs from the folder name and a `part_id` with a path separator each raise.

DO NOT: add a fallback part ID. Do not read the answer file here.

ACCEPTANCE: `uv run pytest tests/test_evals_task.py -q` -> all pass; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

DEPENDS ON: T4.01.

## T4.03 — Answer loader and the fixed five-key schema

GOAL: One loader for the correct answer of a task, with the schema locked at five keys.

FILES (only these): `aturb/evals/answer.py`, `tests/test_evals_answer.py`

DO EXACTLY:

1. Create `aturb/evals/answer.py` with a frozen dataclass `AnswerSpec` (task_id, part_id, expect_file, required_checks, max_score) and a function `load_answer(task_dir: Path) -> AnswerSpec`.
2. The loader reads `<task_dir>/answer.toml`. It accepts exactly the five keys of the answer schema: a missing key or an unknown key raises `ValueError`.
3. `expect_file` must be a relative path that stays inside the task project; `required_checks` must be a non-empty list of names; `max_score` must be a positive number.
4. Create `tests/test_evals_answer.py`: the committed task loads; a file with six keys, a file with four keys, an absolute `expect_file` and an empty `required_checks` each raise.

DO NOT: add a sixth key. Do not add a geometry field.

ACCEPTANCE: `uv run pytest tests/test_evals_answer.py -q` -> all pass.

DEPENDS ON: T4.02.

## T4.04 — Task result type

GOAL: One result type for one task, so a batch result is a list of the same thing.

FILES (only these): `aturb/evals/result.py`, `tests/contract/test_evals_result.py`

DO EXACTLY:

1. Create `aturb/evals/result.py` with a frozen dataclass `TaskResult` (task_id, part_id, status, score, error) and a `to_dict`.
2. `status` is `ok`, `failed` or `error`; `score` is a float from 0.0; `error` is a string that is empty when the task passed; `part_id` is the empty string when the task file could not be read.
3. Create `tests/contract/test_evals_result.py`: the three statuses are accepted, another status raises, and `to_dict` returns the five fields.

DO NOT: add a CAD concept, a geometry field or a sixth field.

ACCEPTANCE: `uv run pytest tests/contract/test_evals_result.py -q` -> all pass.

DEPENDS ON: T4.02.

## T4.05 — Scoring against the required checks

GOAL: One rule that turns neutral check results into the score of a task.

FILES (only these): `aturb/evals/scoring.py`, `tests/test_evals_scoring.py`

DO EXACTLY:

1. Create `aturb/evals/scoring.py` with a function `score_task(answer: AnswerSpec, checks: list[CheckResult]) -> tuple[float, str]` that returns the score and an error text.
2. The score is `max_score * passed / len(required_checks)`. A required check that is missing from the results counts as failed, and the error text names the checks that did not pass.
3. Create `tests/test_evals_scoring.py`: every required check passing gives the full score; one failing check lowers the score in proportion; a missing required check counts as failed.

DO NOT: change the neutral checks. Do not add a weight per check.

ACCEPTANCE: `uv run pytest tests/test_evals_scoring.py -q` -> all pass.

DEPENDS ON: T4.03, T4.04.

## T4.06 — `run_task()`: the build request and the build project

GOAL: One function that builds the part of one task and scores it, with the request built exactly as D2 of the roadmap says.

FILES (only these): `aturb/evals/runner.py`, `tests/test_evals_runner.py`

DO EXACTLY:

1. Create `aturb/evals/runner.py` with `run_task(task_dir: Path, runner: Runner, timeout_s: int) -> TaskResult`. There is no `project_root` parameter.
2. The build project is `(task_dir / "project").resolve()`. The request is built exactly as in D2: `project_root` is that path, `part_id` is `spec.part_id`, `language` is `runner.info().language`, `outputs` is `("native", "step")` and `timeout_s` is the argument.
3. The function loads the task file and the answer file first. A missing or invalid `task.toml` returns an error result whose task ID is the folder name and whose `part_id` is the empty string; a missing or invalid `answer.toml` returns an error result whose task ID is the task ID of the task file.
4. A missing `project/` folder returns an error result.
5. The function builds the part through the runner, then loads the expectation file named by `expect_file` and the STEP from the build project, runs the neutral checks over it and scores them. The expectation file must hold all five expected values. A failed build returns a failed result with score 0.0.
6. Create `tests/test_evals_runner.py` with the stub pack: the committed task builds and scores 1.0; the request that reaches the runner carries `part_id = "plt0001"` and a `project_root` that ends with `plate_2holes/project`; a task folder without `task.toml` returns an error result whose task ID is the folder name.

DO NOT: add a `project_root` parameter. Do not fall back to the task ID as a part ID. Do not change the runner contract.

ACCEPTANCE: `uv run pytest tests/test_evals_runner.py -q` -> all pass; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

DEPENDS ON: T4.02, T4.03, T4.04, T4.05.

## T4.07 — Batch runner that keeps malformed tasks

GOAL: Run every task folder of a set and return one result per folder.

FILES (only these): `aturb/evals/batch.py`, `tests/test_evals_batch.py`

DO EXACTLY:

1. Create `aturb/evals/batch.py` with `run_batch(tasks_root: Path, runner: Runner, timeout_s: int) -> list[TaskResult]`.
2. The batch lists the immediate subfolders of `tasks_root`, sorted by name, and calls `run_task()` for each. It never skips a folder and never stops at the first error.
3. The list holds exactly one result per task folder, in the same order.
4. Create `tests/test_evals_batch.py`: a set of two good tasks gives two results; a set with one folder without `task.toml` and one folder with an invalid `task.toml` gives two error results whose task IDs are the folder names, and the good task is still scored.

DO NOT: skip a malformed task. Do not raise out of the batch.

ACCEPTANCE: `uv run pytest tests/test_evals_batch.py -q` -> all pass.

DEPENDS ON: T4.06.

## T4.08 — Dated result records

GOAL: Write the results of a run to a dated file, so a run can be compared with a later one.

FILES (only these): `aturb/evals/report.py`, `tests/test_evals_report.py`

DO EXACTLY:

1. Create `aturb/evals/report.py` with `write_results(results_dir: Path, results: list[TaskResult]) -> Path` and `read_results(path: Path) -> list[TaskResult]`.
2. The writer writes one file named `<YYYY-MM-DD>_<HHMMSS>.toml` in `results_dir`, with one `[[results]]` record per result, in the order of the results.
3. Create `tests/test_evals_report.py`: a written file holds one record per result, an error result keeps its task ID and its error text, and reading the file back gives the same results.

DO NOT: add a field to the record. Do not write outside `results_dir`.

ACCEPTANCE: `uv run pytest tests/test_evals_report.py -q` -> all pass.

DEPENDS ON: T4.07.

## T4.09 — CLI: `aturb eval`

GOAL: Run a task set from the terminal and print what happened.

FILES (only these): `aturb/cli.py`, `tests/test_cli.py`

DO EXACTLY:

1. Add an `aturb eval <tasks_dir> [--config PATH] [--results-dir DIR]` subcommand. It loads the active pack the way `build` does, runs the batch and writes the dated result file.
2. Print one line per task: `task <task_id> <status> score=<score>`, and the error text on the next line when the task failed or errored. Print a summary line with the number of tasks, the number that passed, the number that failed, the number that errored and the total score.
3. Return 0 when every task is `ok`, 1 when any task failed or errored, and 2 for a configuration or pack error.
4. Add tests to `tests/test_cli.py` with the stub pack: a good task set returns 0 and prints the summary; a set with a malformed task returns 1 and still prints a line for that task.

DO NOT: call a model. Do not add a retry loop. Do not change the `build` or `check` commands.

ACCEPTANCE: `uv run pytest tests/test_cli.py -q` -> all pass; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

DEPENDS ON: T4.08.

## T4.10 — Documentation and the decision record

GOAL: The repository says what a task is, and why a task ID and a part ID are two things.

FILES (only these): `evals/README.md`, `docs/ARCHITECTURE.md`, `docs/adr/0006-task-identity-and-answer-schema.md`

DO EXACTLY:

1. Rewrite `evals/README.md` with the layout of the task set, the four keys of `task.toml`, the five keys of `answer.toml` and the result record.
2. Add a short section to `docs/ARCHITECTURE.md` about the task set and the scoring rule. Keep the file under 130 lines.
3. Write `docs/adr/0006-task-identity-and-answer-schema.md`: the task ID and the part ID are separate, the build project is the task's own `project/` folder, a malformed task is an error result, and the answer schema has five keys and does not grow in Phase 4.

DO NOT: change the runner contract. Do not add a sixth answer key.

ACCEPTANCE: `docs/ARCHITECTURE.md` has under 130 lines; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

DEPENDS ON: T4.09.

## T4.11 — Phase 4 acceptance

GOAL: Prove the phase is green and that nothing outside it moved.

FILES (only these): none; this card only runs commands and reports.

DO EXACTLY:

1. Run the full acceptance list: `uv run pytest -m "not freecad" -q`, `uv run pytest -q`, `uv run ruff check .`, `uv run python tools/size_limit.py`, `uv run python tools/agnostic_lint.py`.
2. Run `git status --short` and `git diff --stat` and check that the changed files are the ones the cards listed.
3. Report the output of every command.

DO NOT: change a file to make a command pass.

ACCEPTANCE: every acceptance command passes; the report lists the changed files.

DEPENDS ON: T4.10.
