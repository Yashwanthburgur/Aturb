# ADR-0006: Task identity and answer schema

Date: 2026-11-20
Status: Accepted

## Context

A task set holds tasks that a candidate tries to build. The task is the unit of
the set and of the report; the part is the unit the runner builds. The two
names are not the same thing, and the answer file holds the correct answer and
must stay unreadable to the candidate.

## Decision

The task ID and the part ID are separate identifiers. The task ID is the name of
the task folder and is repeated in [`task.toml`](../../evals/tasks/plate_2holes/task.toml);
the part ID names the part inside the task project and is never derived from
the task ID.

The build project of a task is always the task's own
[`project/`](../../evals/tasks/plate_2holes/project/) folder, never a folder
passed in and never the working directory of the caller.

A malformed task becomes an error result. It is never skipped:
[`run_batch()`](../../aturb/evals/batch.py:20) holds exactly one result per task
folder, in the order of the folder names, and
[`run_task()`](../../aturb/evals/runner.py:40) turns a task file that cannot be
read into an error result whose task ID is the folder name.

The answer schema has exactly five keys — `task_id`, `part_id`, `expect_file`,
`required_checks` and `max_score` — and does not grow during Phase 4.

## Consequences

A task can be renamed without renaming the part it builds, and one part can be
built by more than one task. A broken task folder still shows up in the report,
so a run never looks complete when it was not. The answer file carries nothing
else, so the scoring rule stays the one rule of the phase:
`max_score * passed_required_checks / total_required_checks`.
