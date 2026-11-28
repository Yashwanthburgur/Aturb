# Architecture

```text
  CLIENTS (thin, one per front end)
    CLI: aturb build | check | assemble | edit-assembly | eval | generate | view
    Browser viewer: clients/viewer/  (zero-build, offline, loopback-only HTTP)
                           |
                  CORE SERVICE (CAD-neutral, language-neutral)
         request -> plan -> edit files -> run -> verify -> fix/finish
         project workspace + history | model access | approval | cost caps
                           |
                    RUNNER CONTRACT  (the only door to a CAD system)
                           |
           BACKEND PACK: packs/freecad | packs/stub | others later
                           |
                  Neutral measuring on exported STEP
```

## Clients

The clients are thin and they exist. Each one only forwards a request to the
core service and shows what comes back. None of them contains CAD knowledge or
geometry logic.

- **The command line** is the client of the core. Every subcommand takes
  `--config`, and the exit codes are the same everywhere: `0` is success, `1`
  is a failed build, check, task or generation, and `2` is a configuration,
  pack or input error.
- **The browser viewer** lives in [`clients/viewer/`](../clients/viewer/). It is
  plain HTML, CSS and JavaScript with the WebGL context of the browser: no
  Node.js, no npm, no bundler and no content delivery network, so it renders
  with no network at all. It serves one workspace over loopback-only HTTP and
  shows the geometry, the measured engineering facts, the revision history and
  the assembly panels.

The core never imports a client, except for the lazy
`from clients.viewer.cli import run_view_command` in the `view` branch of
[`aturb/cli.py`](../aturb/cli.py). The decision is recorded in
[`docs/adr/0011-live-step-viewer-and-client-boundary.md`](adr/0011-live-step-viewer-and-client-boundary.md).

## Core service

The core never knows which CAD, language or front end is in use. It takes a
request, plans the work, edits the project's files, runs them, verifies the
result and either fixes the problem or finishes. It also owns the project
workspace and history, model access, approval and cost caps.

The core is six packages, and each one owns one responsibility:

| package                                   | what it owns                                                                                            |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| [`aturb/contract/`](../aturb/contract/)   | the runner contract: the request, the result and the eight failure kinds                                |
| [`aturb/verify/`](../aturb/verify/)       | the neutral verification layer: the measurements taken from an exported STEP                            |
| [`aturb/agent/`](../aturb/agent/)         | the bounded improvement loop, the model boundary, the prompts and the revision history of a single part |
| [`aturb/assembly/`](../aturb/assembly/)   | the assembly manifest, the assembly build, the coupled edit and the revision history of an assembly     |
| [`aturb/evals/`](../aturb/evals/)         | the task set, the answer schema, the batch runner and the scoring rule                                  |
| [`aturb/workspace/`](../aturb/workspace/) | the paths of a workspace and the atomic single-file persistence                                         |

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

The packs are thin on purpose. A pack selects, measures and asserts; it never creates a
feature on behalf of the agent, and it never holds a rule that the core needs.

## Neutral verification layer

The neutral verification layer lives in the core, in [`aturb/verify/`](../aturb/verify/). It reads an exported STEP file with build123d and measures the geometry from it: the volume, the bounding box, the holes, the gaps and the material that two solids share. It never reads a CAD's own diagnostics, so a check means the same thing in every pack and a backend cannot pass a check by reporting its own success.

The expected values of a part live in the project, in `expect/<part_id>.toml`, and hold numbers only. The layer turns them into check results, and `aturb check` runs them over the exported STEP.

### Engineering and DFM readouts

The same layer answers the engineering questions, independently of any CAD. The
engineering analysis lives in
[`aturb/verify/engineering.py`](../aturb/verify/engineering.py): it measures the
exported STEP and reports the facts an engineer asks for — the validity of the
model, whether it is a single solid, the volume, the bounding box, the holes
with their diameters and positions, and the advisory design-for-manufacturing
findings. The findings are advisories, never verdicts: they never decide
whether a part passes.

### Assembly verification

The assembly verification is independent of the single-part verification and
lives in [`aturb/verify/assembly.py`](../aturb/verify/assembly.py). It composes
the exported STEP of every part into one multi-solid file, places every
component where the manifest says, and reports the verdict of every pair: the
overlap volume and the minimum clearance of the mate. An assembly is verified
as a whole, so a part that is fine on its own can still fail as a member of an
assembly.

## The agent layer

The agent layer lives in [`aturb/agent/`](../aturb/agent/). It writes the
project's CAD code, builds it, measures what it wrote and repairs its own
mistakes inside a bounded loop. The loop is bounded by an attempt limit and by
cumulative token and cost caps, and the stop conditions are checked in a fixed
order. The agent never reads the expectation file: the evaluator is the only
reader of the expected values, so the repair feedback cannot leak the answer.
The decision is recorded in
[`docs/adr/0009-bounded-improvement-loop.md`](adr/0009-bounded-improvement-loop.md).

## Immutable revisions

Every edit is a new immutable revision, never an overwrite in place.

- A single-part workspace keeps its history in
  [`aturb/agent/revisions.py`](../aturb/agent/revisions.py): every revision is
  a `revisions/rNNNN/` folder, `history.toml` names the active one, and a
  rollback selects a verified revision without deleting the later ones.
- An assembly keeps its history in
  [`aturb/assembly/revisions.py`](../aturb/assembly/revisions.py), in the same
  shape, under the output folder of the assembly.

A change is promoted only when it verifies. A rejected edit leaves the live
project byte-for-byte as it was. The decision is recorded in
[`docs/adr/0012-iterative-editing-and-revisions.md`](adr/0012-iterative-editing-and-revisions.md).

## Task set and scoring

A task set is a folder of task folders, one folder per task. Each task folder holds a task file that names the task, an answer file that holds the correct answer, and a `project/` folder that holds the candidate part. The set lives in [`evals/`](../evals/README.md) and the core reads it through [`aturb/evals/`](../aturb/evals/).

The task ID and the part ID are two identifiers. The task ID names the task inside the set and is the name of its folder; the part ID names the part the task builds inside the project. They are allowed to differ, and the part ID is never derived from the task ID. The decision is recorded in [`docs/adr/0006-task-identity-and-answer-schema.md`](adr/0006-task-identity-and-answer-schema.md).

The build project of a task is always the task's own `project/` folder. The answer file stays outside that folder and is never handed to the runner, so a candidate cannot read the correct answer.

The score of a task is `max_score * passed_required_checks / total_required_checks`. Only the checks named in the answer count, and a required check that the results do not hold counts as failed. A task is `ok` when every required check passed, `failed` when the build succeeded and a required check did not pass, and `error` when the task could not be judged at all.

A malformed task is never skipped. The batch runner gives every task folder exactly one result, in the order of the folder names, and a malformed task becomes an error result whose task ID is the folder name and whose part ID is empty. A run therefore always accounts for every folder of the set.

## Two Python environments

The two Python environments, and why they exist, are set out in `docs/adr/0003-two-pythons.md`.
