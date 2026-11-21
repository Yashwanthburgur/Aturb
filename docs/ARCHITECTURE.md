# Architecture

```text
 Clients (later): CLI | FreeCAD panel | cloud agent | messaging
                          |
                 CORE SERVICE (CAD-neutral, language-neutral)
        request -> plan -> edit files -> run -> verify -> fix/finish
        project workspace + history | model access | approval | cost caps
                          |
                   RUNNER CONTRACT  (the only door to a CAD system)
                          |
          BACKEND PACK: FreeCAD (first) | others later
                          |
                 Neutral measuring on exported STEP
```

## Clients

Clients are thin and built later. Each one only forwards a request to the core service and shows what comes back. None of them contains CAD knowledge or geometry logic. The CLI, the FreeCAD panel, a cloud agent and a messaging bot are all clients of the same core.

## Core service

The core never knows which CAD, language or front end is in use. It takes a request, plans the work, edits the project's files, runs them, verifies the result and either fixes the problem or finishes. It also owns the project workspace and history, model access, approval and cost caps.

## Runner contract

The runner contract takes a build request and returns a result, and never exposes CAD operations. It is the only door to a CAD system, so the core never talks to a CAD application directly. Because the contract carries requests and results rather than geometry commands, it stays the same when the CAD changes.

## Runner contract as built

A runner is constructed as `RunnerClass(settings: dict, pack_dir: Path)` and has exactly
two methods: `info()` returns a `PackInfo`, and `build(request)` returns a `BuildResult`.
The types live in [`aturb/contract/types.py`](../aturb/contract/types.py). The eight
failure kinds are `rejected_unsafe`, `syntax_error`, `runtime_error`, `timeout`,
`invalid_geometry`, `export_failed`, `runner_crash` and `input_error`.

A pack is found at `packs/<name>/pack.toml`, for example
[`packs/freecad/pack.toml`](../packs/freecad/pack.toml). Its `runner` key is a
`"module:Class"` string that is imported dynamically, and its `contract_version` is
checked against the core's before the runner is constructed.

The FreeCAD pack runs this sequence: a static precheck of the part file, then a
`job.json` written into the project's output folder, then the CAD executable started as
a subprocess on `harness/build_part.py`, then a `result.json` read back from the same
folder, then artifact paths made relative to the project.

The stub pack copies a packaged fixture STEP instead of building anything. It exists to
prove that the core never needs a CAD.

## Backend pack

A backend pack holds everything for one CAD: its language, its conventions, its prompt and its runner. FreeCAD is the first pack and others come later, one folder per CAD. Adding a CAD means adding a pack, not changing the core.

## Neutral verification layer

The neutral verification layer lives in the core, in [`aturb/verify/`](../aturb/verify/). It reads an exported STEP file with build123d and measures the geometry from it: the volume, the bounding box, the holes, the gaps and the material that two solids share. It never reads a CAD's own diagnostics, so a check means the same thing in every pack and a backend cannot pass a check by reporting its own success.

The expected values of a part live in the project, in `expect/<part_id>.toml`, and hold numbers only. The layer turns them into check results, and `aturb check` runs them over the exported STEP.

## Task set and scoring

A task set is a folder of task folders, one folder per task. Each task folder holds a task file that names the task, an answer file that holds the correct answer, and a `project/` folder that holds the candidate part. The set lives in [`evals/`](../evals/README.md) and the core reads it through [`aturb/evals/`](../aturb/evals/).

The task ID and the part ID are two identifiers. The task ID names the task inside the set and is the name of its folder; the part ID names the part the task builds inside the project. They are allowed to differ, and the part ID is never derived from the task ID. The decision is recorded in [`docs/adr/0006-task-identity-and-answer-schema.md`](adr/0006-task-identity-and-answer-schema.md).

The build project of a task is always the task's own `project/` folder. The answer file stays outside that folder and is never handed to the runner, so a candidate cannot read the correct answer.

The score of a task is `max_score * passed_required_checks / total_required_checks`. Only the checks named in the answer count, and a required check that the results do not hold counts as failed. A task is `ok` when every required check passed, `failed` when the build succeeded and a required check did not pass, and `error` when the task could not be judged at all.

A malformed task is never skipped. The batch runner gives every task folder exactly one result, in the order of the folder names, and a malformed task becomes an error result whose task ID is the folder name and whose part ID is empty. A run therefore always accounts for every folder of the set.

## Two Python environments

The two Python environments, and why they exist, are set out in `docs/adr/0003-two-pythons.md`.
