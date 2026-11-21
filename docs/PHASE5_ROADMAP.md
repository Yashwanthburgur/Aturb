# Phase 5 task roadmap — stock-agent baseline

Proposed task cards for Phase 5, derived from the Phase 4 roadmap
([`docs/PHASE4_ROADMAP.md`](PHASE4_ROADMAP.md)), the architecture
([`docs/ARCHITECTURE.md`](ARCHITECTURE.md)), the decision records
([`docs/adr/`](adr/README.md)) and the runner contract
([`docs/adr/0004-runner-contract.md`](adr/0004-runner-contract.md)).

Scope: one stock LLM agent that writes a candidate CAD part for a task, and the
measurement of that agent on the Phase 4 task set. Phase 4 built the task set
and the scoring rule; Phase 5 puts an agent in front of it and records what the
agent achieved.

## Where this roadmap lives

The implementation guide Part 3 (Phases 5–6) is not in this repository. The
project map in [`docs/IMPLEMENTATION_GUIDE_PART1.md`](IMPLEMENTATION_GUIDE_PART1.md:71)
lists Phase 5 as "Stock-agent baseline", task IDs `T5.xx`, about 32 tasks, in
Part 3. As with Phase 4, the roadmap is split in two, both next to
[`docs/PHASE4_ROADMAP.md`](PHASE4_ROADMAP.md): this file holds the scope, the
decisions and the schemas, and
[`docs/PHASE5_TASKS.md`](PHASE5_TASKS.md) holds the cards T5.01 to T5.14. This
plan proposes 14 cards; the guide's estimate of about 32 is larger, and the
difference is left open in the questions at the end of this file.

## Scope boundaries (locked for Phase 5)

- One agent, one model, one call per task. No multi-agent logic, no agent
  framework, no background summarizer, no design graph
  ([`AGENTS.md`](../AGENTS.md:25)).
- No CAD-operation tools, no geometry DSL, no JSON geometry schema, no
  operations layer ([`AGENTS.md`](../AGENTS.md:23),
  [`docs/adr/0001-code-first.md`](adr/0001-code-first.md)).
- No retry loop and no improvement loop. One model call, one build, one score.
  The improvement loop is Phase 7.
- No runner contract change. [`BuildRequest`](../aturb/contract/types.py:26),
  [`BuildResult`](../aturb/contract/types.py:58), [`PackInfo`](../aturb/contract/types.py:113)
  and [`Runner`](../aturb/contract/runner.py:10) stay as they are, the contract
  version is not bumped and no failure kind is added.
- No change to the Phase 4 task format, the five-key answer schema, the
  evaluator, the scoring rule or the five-field result record. A change to any
  of them needs a decision record.
- No GUI and no new client. The CLI is the only surface.
- No new dependency. The model call uses the standard library, so
  [`pyproject.toml`](../pyproject.toml) and [`uv.lock`](../uv.lock) do not move.
- No unverified API. The model API is verified in-session and recorded in
  [`docs/api_notes/`](api_notes/README.md) before any client code is written
  ([`AGENTS.md`](../AGENTS.md:28)).

## Decisions

### D1 — The agent is a pure text-to-text function

The agent takes one prompt and returns the text of one part file. It has no
filesystem access, no tools, no shell and no memory between tasks. The core
composes the prompt, calls the model, and writes what comes back. This is what
makes the isolation of D2 true by construction rather than by policy: a
function that cannot read a file cannot read the reference solution.

### D2 — The reference solution never reaches the agent

The committed task holds the hand-written correct part at
[`evals/tasks/plate_2holes/project/parts/plt0001_base_plate.py`](../evals/tasks/plate_2holes/project/parts/plt0001_base_plate.py).
The agent must not read it and must not be scored against it.

- The agent receives only the composed prompt. The reference part file is never
  read by the agent path and never enters the prompt.
- The agent writes into a scratch copy of the task, never into the committed
  task folder. The committed task set stays pristine and re-runnable.
- The scratch copy holds `task.toml`, `answer.toml` and the project folders
  `expect/` and `requirements/`, and an **empty** `parts/` folder. The
  reference part file is not copied.

### D3 — The candidate workspace is a scratch task folder

The scratch folder has the same shape as a task folder, so the Phase 4
evaluator runs on it unchanged:

```text
<work_dir>/<task_id>/
  task.toml        # copied
  answer.toml      # copied, never shown to the agent
  project/
    parts/         # empty; the agent writes one file here
    expect/        # copied
    requirements/  # copied
    out/           # written by the runner
```

[`run_task()`](../aturb/evals/runner.py:40) takes a task folder and derives the
build project from it, so the scratch folder is scored by the existing code with
no change at all. The result carries the same task ID and part ID as the
original task. The work directory is `evals/tmp/agent/`, which
[`.gitignore`](../.gitignore:20) already excludes; a failed candidate stays on
disk so it can be read.

### D4 — The agent boundary is CAD-neutral

The new code lives in `aturb/agent/` and never names a CAD system. The
agnosticism lint scans `aturb/` for CAD terms
([`tools/agnostic_lint.py`](../tools/agnostic_lint.py:14)), so the following
come from the pack, never from the core:

| what                                | where it comes from                                                         |
| ----------------------------------- | --------------------------------------------------------------------------- |
| the language tag                    | [`PackManifest.language`](../aturb/packs.py:36) or `runner.info().language` |
| the part file extension             | [`PackManifest.part_extension`](../aturb/packs.py:37)                       |
| the prompt folder                   | [`PackManifest.prompt_dir`](../aturb/packs.py:39)                           |
| the file contract and the API calls | the pack prompt file                                                        |

`prompt_dir` is already a required key of every pack manifest
([`aturb/packs.py`](../aturb/packs.py:17)) and is read by nothing today. Phase 5
is its first consumer.

### D5 — The pack owns the prompt instructions

Each pack that can be used by the agent holds one prompt file at
`packs/<name>/prompt/agent.md`. The core reads it as opaque text and never
interprets it.

- The pack prompt states the file contract of the pack's language, the verified
  API calls the agent may use, and the output contract.
- The verified calls are the rows of [`docs/api_notes/`](api_notes/README.md).
  The pack prompt cites the task IDs of the rows it uses, and a test checks that
  every cited ID exists in the matching API note.
- The stub pack gets a minimal prompt of its own, so the whole agent path can
  be tested without a CAD.

### D6 — The model provider is configured, not hard-coded

The provider, the model, the endpoint and the limits come from the `[agent]`
section of the configuration. The core holds a `ModelClient` protocol and one
HTTP implementation; the provider name selects the implementation.

- The API key is **never** in the configuration file. The configuration names
  an environment variable, and the core reads the key from the environment.
- The key never reaches the part process. The FreeCAD runner already passes a
  minimal environment to the child ([`docs/SECURITY.md`](SECURITY.md:11)).
- The HTTP call uses `urllib.request` from the standard library. No new
  dependency, no new lock file entry, nothing to verify beyond the standard
  library.

### D7 — The prompt is composed in a fixed order and versioned by its hash

The composed prompt is, in this order: a fixed core instruction block, written
by the core and CAD-neutral; the pack prompt file; the task requirement text
from `project/requirements/`; the expected values from `project/expect/`; and
the output contract, which asks for the file content and nothing else.

The prompt version is the SHA-256 of the exact text sent to the model, cut to
16 hex characters. A hash needs no registry, cannot drift from the text, and
changes whenever anything in the prompt changes. The agent-run record stores it.

The model is asked for the file content only. The core strips one optional
markdown fence and nothing else; there is no other parsing of model output.

### D8 — The candidate file has one name and one place

The candidate is written to `project/parts/<part_id>_candidate<extension>` in
the scratch project, where the extension comes from the pack manifest. The
runner finds the part by globbing `<part_id>_*<extension>`
([`packs/freecad/runner.py`](../packs/freecad/runner.py:37),
[`packs/stub/runner.py`](../packs/stub/runner.py:53)), so one file with one
name is unambiguous. The reference file is not in the scratch project, so there
is exactly one match and the runner never reports an ambiguous part.

### D9 — The agent run has its own record, separate from the task result

The Phase 4 result record has exactly five fields and is frozen. The agent run
needs more: the model, the prompt version, the tokens, the cost and the
attempts. It therefore gets its own type and its own file.

```toml
[[runs]]
task_id = "plate_2holes"
part_id = "plt0001"
provider = "openai_compatible"
model = "some-model-id"
prompt_version = "3f2a1c9d0e4b5a67"
input_tokens = 812
output_tokens = 431
cost_usd = 0.0041
attempts = 1
status = "ok"
error = ""
```

- The file is `evals/results/<YYYY-MM-DD>_<HHMMSS>_agent.toml`, next to the
  Phase 4 result file of the same run, so one timestamp pairs the two.
- `status` is `ok` or `error` and describes the **agent**, not the geometry.
  The geometry status is the Phase 4 `ok`/`failed`/`error` in the result file.
- `attempts` is always `1` in Phase 5. The field exists so Phase 7 can use the
  same record without changing it.
- The answer schema stays at five keys and the result record stays at five
  fields. Neither grows.

### D10 — The limits are token caps first, and a budget when prices are known

- `max_input_tokens` and `max_output_tokens` are hard caps. A prompt over the
  input cap is refused before the call; the output cap is sent with the
  request.
- `max_cost_usd` is a budget for one run. It is checked before the call, using
  the configured prices, and the actual cost is computed from the reported
  usage afterwards.
- Prices live in the local configuration, because they change and must not be
  frozen in the repository. When no price is configured the cost is `0.0` and
  the dollar budget is not enforced; the token caps still are.
- Every failure is a result, never an exception: a missing requirement file, a
  missing pack prompt, a refused budget, a failed call and an empty answer all
  give an agent run with `status = "error"` and an error text.

### D11 — The agent plugs into the existing evaluation pipeline

The CLI gains one flag: `aturb eval <tasks_dir> [--agent]`.

- Without `--agent`, the command behaves exactly as it does today. The
  existing CLI tests must pass unchanged.
- With `--agent`, each task folder is copied to the scratch area, the agent
  writes the candidate there, and the existing [`run_task()`](../aturb/evals/runner.py:40)
  builds and scores it. The Phase 4 result file is written by the existing
  [`write_results()`](../aturb/evals/report.py:36) and keeps its format.
- The exit codes do not change: `0` when every task is `ok`, `1` when any task
  is `failed` or `error`, `2` for a configuration or pack error.

### D12 — A baseline is a recorded measurement, not a deterministic function

A model call is not reproducible. What is reproducible is the measurement: the
model, the prompt version, the task set and the date are recorded, so a later
run can be compared with it. A baseline is identified by the tuple (model,
prompt version, task set) and is written down in `docs/PHASE5_BASELINE.md` with
the commands that produced it. There is no leaderboard and no task index:
Phase 4 excluded both, and Phase 5 does not add them.

## The agent-run record

The record is written by the agent, not by the task author, so it is not the
answer schema and not the result record. Its fields are:

| field            | meaning                                          |
| ---------------- | ------------------------------------------------ |
| `task_id`        | the task the run belongs to                      |
| `part_id`        | the part the task builds                         |
| `provider`       | the provider implementation that made the call   |
| `model`          | the model identifier sent with the request       |
| `prompt_version` | the SHA-256 prefix of the exact prompt text      |
| `input_tokens`   | the input tokens the provider reported           |
| `output_tokens`  | the output tokens the provider reported          |
| `cost_usd`       | the cost computed from the configured prices     |
| `attempts`       | the number of model calls; always `1` in Phase 5 |
| `status`         | `ok` or `error`, about the agent                 |
| `error`          | why the run failed; empty for `ok`               |

## Configuration

The `[agent]` section of the local configuration file. The file is gitignored
([`.gitignore`](../.gitignore:9)), so nothing here is committed.

```toml
[agent]
provider = "openai_compatible"          # starting default
model = ""                              # the model identifier to send
base_url = ""                           # the endpoint of the provider
api_key_env = "ATURB_AGENT_API_KEY"     # starting default
max_input_tokens = 20000                # starting default
max_output_tokens = 8000                # starting default
max_cost_usd = 0.50                     # starting default
input_price_per_mtok = 0.0              # starting default
output_price_per_mtok = 0.0             # starting default
timeout_s = 120                         # starting default
```

The key itself is never written in this file. The core reads the environment
variable named by `api_key_env`.

## Dependency order

T5.01 → T5.02 → T5.03 → T5.04 → T5.05 → T5.06 → T5.07 → T5.08 → T5.09 → T5.10
→ T5.11 → T5.12 → T5.13 → T5.14

T5.03 (the API spike) may run in parallel with T5.01 and T5.02. T5.04 waits
for T5.03, because the client may only use calls that were verified and
recorded. Every other card waits for the card before it. The cards are in
[`docs/PHASE5_TASKS.md`](PHASE5_TASKS.md).

## Not in Phase 5

- A second agent, an agent framework, a tool loop or a memory between tasks.
- A retry loop, a repair loop or any improvement loop. That is Phase 7.
- A change to the runner contract, a new failure kind or a version bump.
- A sixth answer key, a sixth result field, a geometry field, a geometry DSL or
  an operations layer.
- A GUI, a panel, a new client or a cloud agent.
- A leaderboard, a task index, a task generator or a second task.
- A new dependency, a new lock file entry or a vendored SDK.

## Open questions

- The guide estimates about 32 tasks for Phase 5
  ([`docs/IMPLEMENTATION_GUIDE_PART1.md`](IMPLEMENTATION_GUIDE_PART1.md:71));
  this plan proposes 14 cards. The difference is left open: the cards are the
  plan that was carried out, and the estimate of the guide was not revised.
