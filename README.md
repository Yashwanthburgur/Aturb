# ATURB

ATURB is an AI agent that does mechanical CAD work on a person's behalf. You
describe a part, a change or an assembly edit in plain language. The agent
writes the project's CAD code, builds it in a real CAD system through a pack,
checks the result with neutral measurements it cannot influence, repairs its
own mistakes within a bounded loop, and presents a verified result you can
inspect, approve or undo.

ATURB is not a CAD program, not a text-to-mesh generator, not tied to one CAD
vendor, and not a replacement for an engineer's sign-off.

## What is in the repository today

| area        | what it is                                                                                                                                                     |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `aturb/`    | the CAD-neutral core: the runner contract, the neutral verification layer, the agent loop, the assembly layer, the evaluation runner and the workspace helpers |
| `packs/`    | the backend packs: `packs/freecad/` builds real geometry headless, `packs/stub/` copies a packaged fixture and needs no CAD at all                             |
| `clients/`  | the thin clients of the core: `clients/viewer/` is a zero-build, offline browser viewer served over loopback-only HTTP                                         |
| `evals/`    | the task sets: 10 single-part tasks in `evals/tasks/` and 2 coupled multi-part assembly tasks in `evals/assemblies/`                                           |
| `projects/` | example projects, including the demo project                                                                                                                   |
| `docs/`     | the architecture, the security model, the environment notes, the API notes and the decision records                                                            |
| `tools/`    | the lints and the size limit that guard the repository                                                                                                         |

## Core architectural invariants

1. **The core is CAD-neutral and language-neutral.** Everything specific to one
   CAD system lives in `packs/<name>/`. The core never names a backend.
2. **One runner contract.** A runner takes a build request and returns a build
   result. It never exposes CAD operations, so the contract survives a change
   of CAD.
3. **Correctness is judged only from the exported STEP.** The neutral
   verification layer measures the geometry itself, so a backend cannot pass a
   check by reporting its own success.
4. **The model writes CAD code.** There is no intermediate geometry language,
   no JSON geometry schema, no DSL and no agent-callable operations layer.
5. **Pack helpers select, measure and assert.** They never create a feature.
6. **The agent never reads the expectation file.** The evaluator is the only
   reader of the expected values, so the repair feedback cannot leak the
   answer.
7. **Every edit is an immutable revision.** A rollback selects a verified
   revision and never deletes the later ones.
8. **The viewer is a client.** The core gains no HTML, no CSS, no JavaScript
   and no HTTP server; the client imports the core, never the other way round.

## Quickstart

```text
uv sync
copy aturb.example.toml aturb.local.toml
```

Then edit `aturb.local.toml`: set `active_pack`, point `[packs.freecad] cmd`
at the command-line executable of your CAD installation (see
[`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md)), and fill in the `[agent]`
section with the provider, the model and the endpoint.

The API key is never written in the configuration file. The core reads it from
the environment variable that `api_key_env` names:

```text
set ATURB_AGENT_API_KEY=<your key>
```

Then build and check a part:

```text
uv run aturb build projects/demo plt0001
uv run aturb check projects/demo plt0001
```

## Commands

Every subcommand accepts `--config`, so one configuration file drives the whole
tool. The exit codes are the same everywhere: `0` is success, `1` is a failed
build, a failed check, a failed task or an unsuccessful generation, and `2` is
a configuration, pack or input error.

| command               | positional arguments                        | options                                                                  | exit codes                                                                            |
| --------------------- | ------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| `aturb build`         | `project_dir` `part_id`                     | `--config`                                                               | `0` built, `1` build failed, `2` config or pack error                                 |
| `aturb check`         | `project_dir` `part_id`                     | `--config`                                                               | `0` every check passed, `1` a check failed, `2` config or pack error                  |
| `aturb assemble`      | `project_dir` `assembly_file`               | `--config`                                                               | `0` assembled and verified, `1` the assembly failed, `2` config or pack error         |
| `aturb edit-assembly` | `project_dir` `assembly_file` `instruction` | `--config`                                                               | `0` edited and promoted, `1` the edit was refused, `2` config, pack or agent error    |
| `aturb eval`          | `tasks_dir`                                 | `--config` `--results-dir` `--agent`                                     | `0` every task is `ok`, `1` a task failed or errored, `2` config, pack or input error |
| `aturb generate`      | `[prompt]`                                  | `--prompt-file` `--out` `--part-id` `--max-attempts` `--config` `--pack` | `0` generated, `1` the generation was unsuccessful, `2` config, pack or input error   |
| `aturb view`          | `workspace`                                 | `--config`                                                               | `0` the viewer stopped cleanly, `2` the workspace or the port was refused             |

`aturb eval --agent` runs the bounded agent loop over the task set instead of
building the committed candidates. `aturb generate` takes either a positional
prompt or `--prompt-file`, never both.

## Benchmarks

### The committed test and evaluation suite

These numbers are reproducible from a clean checkout and are what the
repository's own commands report.

- **1,080 tests are collected: 1,078 pass and 2 skip.** 47 of them are marked
  `freecad` and build real geometry in FreeCAD 1.0.1; the other 1,033 run
  with no CAD installed at all.
- **The evaluation suite holds 10 single-part tasks** in `evals/tasks/` and
  **2 coupled multi-part assembly tasks** in `evals/assemblies/`. The six
  multi-feature single-part tasks are `bossed_plate_pocket`,
  `enclosure_housing`, `flanged_hub_counterbore`, `l_bracket_chamfer`,
  `ribbed_l_bracket` and `stepped_shaft`.

The commands that produce those numbers:

```text
uv run pytest -q
uv run pytest -m "not freecad" -q
uv run ruff check .
uv run python tools/size_limit.py
uv run python tools/agnostic_lint.py
```

### Observed live-model runs

**These are evidence from observed runs on the development machine, not a
committed CI guarantee.** They depend on a live provider, a live CAD
installation and a network, so no command in this repository reproduces them
offline and no test asserts them.

Against the model `minimaxai/minimax-m3.1-flash`:

- **6 of 6 complex single-part tasks scored `1.0`** in the Phase 11 run.
- **2 of 2 coupled assembly edits passed on Attempt 1** in the Phase 14 run.
  The edited `bushing_in_housing` assembly measured `133553.393334` mm³ in a
  bounding box of `80.0 x 80.0 x 26.5` mm, and the edited
  `pin_in_plate_upsize` assembly measured `70479.096455` mm³ in a bounding box
  of `100.0 x 60.0 x 23.5` mm. Both kept a radial clearance of `0.200 mm` and
  showed no interference.

The expected values those runs are judged against are committed, in
`evals/assemblies/*/expected_edit.toml` and in the `expect/` folder of every
task. The provider call itself is recorded in
[`docs/api_notes/model.md`](docs/api_notes/model.md).

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the layers, the runner
  contract, the verification layer and the scoring rule.
- [`docs/SECURITY.md`](docs/SECURITY.md) — the build sandbox and the loopback
  viewer server model, and what is explicitly not guaranteed.
- [`docs/adr/README.md`](docs/adr/README.md) — the decision records, one per
  decision.
- [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md) — the machine, the tools and the
  CAD installation this repository was verified on.
- [`AGENTS.md`](AGENTS.md) — the rules a coding agent must follow in this
  repository.
