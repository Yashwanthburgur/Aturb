# Evaluation tasks

A task set is a folder of task folders. Each task folder holds one task: the
task file that names it, the answer file that says what a correct build looks
like, and the project folder that holds the candidate part.

## Layout

```text
evals/
  tasks/
    plate_2holes/
      task.toml
      answer.toml
      project/
        parts/          the candidate part file
        requirements/   the engineering prompt
        expect/         the expected values the checks read
        out/            build artifacts, written by the runner
  results/
    2026-11-20_101500.toml
```

Every immediate subfolder of `tasks/` is one task. The folder name is the task
ID, and the task file has to repeat it.

## task.toml — four keys

| key           | meaning                                             |
| ------------- | --------------------------------------------------- |
| `task_id`     | the name of the task; it must equal the folder name |
| `part_id`     | the part the task builds; a plain token             |
| `name`        | a short human-readable title                        |
| `description` | a human-readable summary of the task                |

The task ID and the part ID are two different things. The task ID names the
task inside the set; the part ID names the part inside the project. They are
allowed to differ, and in the committed task they do: the task is
`plate_2holes` and the part is `plt0001`. A missing key, an unknown key, a
`task_id` that differs from the folder name, or a `part_id` that is not a plain
token makes the task malformed. The loader is
[`load_task()`](../aturb/evals/task.py:45).

## answer.toml — five keys

| key               | meaning                                                                            |
| ----------------- | ---------------------------------------------------------------------------------- |
| `task_id`         | the task the answer belongs to; it must match `task.toml`                          |
| `part_id`         | the part the answer belongs to; it must match `task.toml`                          |
| `expect_file`     | the expectation file, relative to the task project and inside its `expect/` folder |
| `required_checks` | the names of the checks that must pass                                             |
| `max_score`       | the score a fully correct answer earns                                             |

The answer file has exactly these five keys. A missing key or an unknown key
makes the answer malformed. The answer file stays outside the candidate
project and is never handed to the runner: the runner only ever sees the build
request of the runner contract. The loader is
[`load_answer()`](../aturb/evals/answer.py:53).

## The result record

One task gives one result, and a result holds exactly five fields:

| field     | meaning                                           |
| --------- | ------------------------------------------------- |
| `task_id` | the task the result belongs to                    |
| `part_id` | the part the task builds                          |
| `status`  | `ok`, `failed` or `error`                         |
| `score`   | the score of the task, from 0.0 up to `max_score` |
| `error`   | why the task did not pass; empty for `ok`         |

`ok` means the build succeeded and every required check passed. `failed` means
the build succeeded but at least one required check did not pass. `error` means
the task could not be judged at all: a malformed task or answer, a failed
build, or a STEP file that could not be read. The type is
[`TaskResult`](../aturb/evals/result.py:30).

The score of a task is

```text
max_score * passed_required_checks / total_required_checks
```

Only the checks named in `required_checks` count. A required check that the
results do not hold counts as failed, and a check that is not required is
ignored. The rule lives in [`score_task()`](../aturb/evals/scoring.py:25).

## Running a task set

```text
aturb eval <tasks_dir> [--config PATH] [--results-dir DIR]
```

The command loads the active pack the same way `aturb build` does, builds and
scores every task folder of the set, writes the results to a dated file and
prints one line per task:

```text
task plate_2holes ok score=1.0
summary tasks=1 passed=1 failed=0 errored=0 score=1.0
```

A task that is `failed` or `error` prints its error text on the next line. The
exit code is `0` when every task is `ok`, `1` when any task is `failed` or
`error`, and `2` for a configuration or pack error.

## The dated result file

The results of a run are written to one TOML file in the results folder, named
after the date and the time of the run:

```text
evals/results/<YYYY-MM-DD>_<HHMMSS>.toml
```

The results folder is the `results/` folder next to the tasks folder, unless
`--results-dir` names another one. The file holds one `[[results]]` record per
task, in the order of the tasks, and every record holds exactly the five fields
of a result:

```toml
[[results]]
task_id = "plate_2holes"
part_id = "plt0001"
status = "ok"
score = 1.0
error = ""
```

A later run writes a new file, so two runs can be compared. The writer is
[`write_results()`](../aturb/evals/report.py:36) and the reader is
[`read_results()`](../aturb/evals/report.py:55).
