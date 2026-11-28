# Phase 7 baseline — one measured run of the bounded repair loop

Date of the run: **2026-11-23**, 06:46 local time (Asia/Calcutta).
Task card: T7.12.

This file is a record of one run. It is not a promise and not a target.

## What was run

- Task set: [`evals/tasks`](../evals/tasks) — four committed task folders:
  [`plate_2holes`](../evals/tasks/plate_2holes),
  [`plate_fillet`](../evals/tasks/plate_fillet),
  [`plate_pocket`](../evals/tasks/plate_pocket) and
  [`plate_step`](../evals/tasks/plate_step).
- Pack: `freecad`, the active pack of the local configuration, FreeCAD 1.0.1.
- Provider: `nvidia` — NVIDIA-hosted, OpenAI-compatible Chat Completions.
- Model: `nvidia/nemotron-3.5-super-vl-120b-a12b`.
- Agent: the bounded repair loop of
  [`run_agent_loop()`](../aturb/agent/loop.py:100), up to three attempts per
  task, bounded by the cumulative token and cost budgets of
  [`DEFAULTS`](../aturb/agent/config.py:19).
- The run was made once. Nothing in the implementation was changed before or
  after it to make the result look better.

**The prompt version of the first attempt is the Phase 6 prompt version.** The
first prompt of a task is byte-identical to the prompt of the Phase 6 baseline,
so the two tasks that Phase 6 already ran carry the Phase 6 version. The two
tasks that Phase 7 added have no Phase 6 counterpart and carry a version of
their own.

| Task           | Prompt version of attempt 1                       | Prompt version of attempt 2            |
| -------------- | ------------------------------------------------- | -------------------------------------- |
| `plate_2holes` | `25830ef6f36acf93` — the Phase 6 version          | `72ff74b2aacf8db5` — the repair prompt |
| `plate_fillet` | `ca0607a60b7eacb6` — the Phase 6 version          | —                                      |
| `plate_pocket` | `6780598d37967c98` — new task, no Phase 6 version | —                                      |
| `plate_step`   | `48dfb0d2194b33f7` — new task, no Phase 6 version | —                                      |

The later prompts carry the repair feedback of the previous attempt: the build
status and failure kind, the sanitized error text, the CAD diagnostics, the
advisory convention findings and the candidate-only geometry summary. They
never carry the expected values of the task, as decided in
[`docs/adr/0008-exclude-expectations-from-prompt.md`](adr/0008-exclude-expectations-from-prompt.md).
Each repair prompt has its own version, computed by
[`prompt_version()`](../aturb/agent/prompt.py:74).

**The bounds of the run.** The `[agent]` section of the local, git-ignored
[`aturb.local.toml`](../aturb.local.toml) sets the per-call bounds; the
cumulative bounds are the starting defaults of
[`DEFAULTS`](../aturb/agent/config.py:19), because the local configuration does
not name them.

| Bound                     | Value | Where it comes from              |
| ------------------------- | ----- | -------------------------------- |
| `max_attempts`            | 3     | starting default, not overridden |
| `max_input_tokens`        | 20000 | local configuration, per call    |
| `max_output_tokens`       | 16000 | local configuration, per call    |
| `max_cost_usd`            | 0.50  | local configuration, per call    |
| `max_total_input_tokens`  | 60000 | starting default, cumulative     |
| `max_total_output_tokens` | 24000 | starting default, cumulative     |
| `max_total_cost_usd`      | 0.75  | starting default, cumulative     |
| `timeout_s`               | 300   | local configuration              |

## The status and the score of every task

| Task           | Part      | Attempt 1    | Final        | Attempts used      | Stop outcome      | Tokens in / out / total | Cost (USD) | Lift |
| -------------- | --------- | ------------ | ------------ | ------------------ | ----------------- | ----------------------- | ---------- | ---- |
| `plate_2holes` | `plt0001` | `failed` 0.6 | `failed` 0.6 | 2 calls, 3 records | `budget_exceeded` | 4768 / 19441 / 24209    | 0.0        | 0.0  |
| `plate_fillet` | `plt0002` | `ok` 1.0     | `ok` 1.0     | 1 call, 1 record   | `passed`          | 2303 / 9238 / 11541     | 0.0        | 0.0  |
| `plate_pocket` | `plt0003` | `error` 0.0  | `error` 0.0  | 1 call, 1 record   | `model_error`     | 0 / 0 / 0               | 0.0        | 0.0  |
| `plate_step`   | `plt0004` | `error` 0.0  | `error` 0.0  | 1 call, 2 records  | `budget_exceeded` | 2399 / 16000 / 18399    | 0.0        | 0.0  |

The lift is the score of the final attempt minus the score of attempt 1. It is
`0.0` for every task of this run: no task was lifted by the repair loop.

The required checks are the five named in
[`answer.toml`](../evals/tasks/plate_2holes/answer.toml:9) and in the three
other answer files; the score is `max_score * passed / required`, so 5 of 5
gives 1.0 and 3 of 5 gives 0.6.

Output of the run command:

```
task plate_2holes failed score=0.6
the checks did not pass: volume, hole_count
task plate_fillet ok score=1.0
task plate_pocket error score=0.0
the model call failed: the nvidia model response has no generated text
task plate_step error score=0.0
'(' was never closed (<unknown>, line 32)
summary tasks=4 passed=1 failed=1 errored=2 score=0.4
```

The summary score of the run is `0.4`, the mean of `0.6`, `1.0`, `0.0` and
`0.0`.

## The token counts and the cost

| Task           | Input tokens | Output tokens | Total tokens | Cost (USD) |
| -------------- | ------------ | ------------- | ------------ | ---------- |
| `plate_2holes` | 4768         | 19441         | 24209        | 0.0        |
| `plate_fillet` | 2303         | 9238          | 11541        | 0.0        |
| `plate_pocket` | 0            | 0             | 0            | 0.0        |
| `plate_step`   | 2399         | 16000         | 18399        | 0.0        |
| All four tasks | 9470         | 44679         | 54149        | 0.0        |

The cost is `0.0` because no price per million tokens is configured: the price
of the tokens of this provider is not known yet, as recorded under "Still
awaiting verification" in
[`docs/api_notes/model.md`](../docs/api_notes/model.md:80). The recorded cost is
the cost the configuration can compute, not a measured bill.

## The run, exactly as it happened

Three of the four tasks did not reach a passing candidate, so the failures are
written down here exactly as they happened.

**Every attempt of the run**, from
`evals/tmp/phase7_baseline/2026-11-23_064654_attempts.toml`:

| Task           | Attempt | Prompt version     | In / out tokens | Status   | Outcome                     | Score | Failed checks          |
| -------------- | ------- | ------------------ | --------------- | -------- | --------------------------- | ----- | ---------------------- |
| `plate_2holes` | 1       | `25830ef6f36acf93` | 2280 / 7728     | `failed` | `checks_failed`             | 0.6   | `volume`, `hole_count` |
| `plate_2holes` | 2       | `72ff74b2aacf8db5` | 2488 / 11713    | `failed` | `checks_failed`             | 0.6   | `volume`, `hole_count` |
| `plate_2holes` | 3       | —                  | 0 / 0           | `error`  | `budget_exceeded`           | 0.0   | —                      |
| `plate_fillet` | 1       | `ca0607a60b7eacb6` | 2303 / 9238     | `ok`     | `passed`                    | 1.0   | —                      |
| `plate_pocket` | 1       | `6780598d37967c98` | 0 / 0           | `error`  | `model_error`               | 0.0   | —                      |
| `plate_step`   | 1       | `48dfb0d2194b33f7` | 2399 / 16000    | `error`  | `build_failed:syntax_error` | 0.0   | —                      |
| `plate_step`   | 2       | —                  | 0 / 0           | `error`  | `budget_exceeded`           | 0.0   | —                      |

The two attempts with no prompt version and no tokens are attempts the loop
refused before it called the model, because the cumulative output-token budget
would have been passed. The errors are the ones of the file:

- `plate_2holes`, attempt 3: `the cumulative output token budget would be
passed: 35441 tokens > 24000`.
- `plate_step`, attempt 2: `the cumulative output token budget would be
passed: 32000 tokens > 24000`.

**The geometry measured from the exported STEP files**, with
[`load_step()`](../aturb/verify/step.py:90) and
[`find_holes()`](../aturb/verify/holes.py:48):

| Part      | Volume (mm³)     | Bounding box (mm) | Solids | Holes                                            |
| --------- | ---------------- | ----------------- | ------ | ------------------------------------------------ |
| `plt0001` | 36000.0          | 120 × 60 × 5      | 1      | none                                             |
| `plt0002` | 35175.9735060141 | 120 × 60 × 5      | 1      | 2 through holes of 10 mm at (−40, 0) and (40, 0) |

`plt0003` has no candidate file and no STEP file: the model call failed before
anything was written. `plt0004` has a candidate file of 32 lines and no STEP
file: the response was cut off and the file does not parse.

The checks of the two candidates that were built, measured with `aturb check`:

```
check volume failed: expected 35214.602, got 36000.0
check bbox_x passed
check bbox_y passed
check bbox_z passed
check hole_count failed: expected 2, got 0
check hole_diameter failed: the model holds no hole to measure
check hole_0 failed: the model holds fewer holes than expected
check hole_1 failed: the model holds fewer holes than expected
```

```
check volume passed
check bbox_x passed
check bbox_y passed
check bbox_z passed
check hole_count passed
check hole_0_diameter passed
check hole_1_diameter passed
check hole_0_x passed
check hole_0_y passed
check hole_1_x passed
check hole_1_y passed
```

Five facts of this run are worth writing down, because they are what it
measured:

- **The repair loop lifted nothing in this run.** `plate_2holes` was judged
  twice and scored 0.6 both times, with the same two checks failing. The
  second attempt was a repair prompt that carried the candidate-only geometry
  of the first attempt, and the candidate it produced still cut no hole.
- **`plate_2holes` cut no hole, as in Phase 5.** The candidate put the hole
  sketch on the Z = 0 plane and cut with `Type = "ThroughAll"`, so the cut went
  away from the material: the measured solid is a plain plate of 36000 mm³
  with no hole in it, against the expected 35214.602 mm³ and two holes.
- **`plate_fillet` passed on the first attempt.** The candidate selected the
  fillet edges with the helper, with
  [`helper.corner_edges()`](../packs/freecad/helper/select.py:61) and
  [`helper.assert_count()`](../packs/freecad/helper/select.py:111), and created
  the `PartDesign::Fillet` feature of
  `evals/tmp/agent/plate_fillet/project/parts/plt0002_candidate.py`
  itself. The helper selected and asserted; it created nothing.
- **`plate_step` never reached the helper.** The response of the model was cut
  off at the 16000 output-token cap of the configuration, so the candidate file
  ends in the middle of an expression and the precheck refused it with
  `'(' was never closed (<unknown>, line 32)`. The repair attempt was then
  refused by the cumulative output-token budget, so the helper was never used
  on this task.
- **The conventions checker is advisory and never blocks a build.**
  [`check_conventions()`](../aturb/agent/conventions.py:65) reports one finding
  for the candidate of `plate_2holes` — `C2: line 11: the parameter block is
not at the top of the file` — and one for the candidate of `plate_fillet` —
  `C2: line 8: the parameter block is not at the top of the file`. The task
  still scored 1.0. The candidate of `plate_step` has no finding, and
  `plate_pocket` has no candidate file to check. The findings are recorded
  here as they were measured, not as they should have been.

The candidate files are not committed. They stay in the git-ignored scratch
folder as
`evals/tmp/agent/plate_2holes/project/parts/plt0001_candidate.py`,
`evals/tmp/agent/plate_fillet/project/parts/plt0002_candidate.py`
and
`evals/tmp/agent/plate_step/project/parts/plt0004_candidate.py`,
and the raw response of the model is not in this repository.

## The exact commands

1. The baseline run. The key is read from the local `.env` into the environment
   variable `NVIDIA_API_KEY`; the key is never printed and never enters the
   repository.

```
powershell -NoProfile -Command "$line = Get-Content .env | Where-Object { $_ -match '^\s*NVIDIA_API_KEY\s*=' } | Select-Object -First 1; $env:NVIDIA_API_KEY = ($line -split '=',2)[1].Trim(); uv run aturb eval evals/tasks --agent --config aturb.local.toml --results-dir evals/tmp/phase7_baseline 2>&1 | Tee-Object -FilePath evals/tmp/phase7_baseline/live_run.log; exit $LASTEXITCODE"
```

2. The checks of the two candidates that were built, to record the geometry in
   detail.

```
uv run aturb check evals/tmp/agent/plate_2holes/project plt0001 --config aturb.local.toml
uv run aturb check evals/tmp/agent/plate_fillet/project plt0002 --config aturb.local.toml
```

3. The inspection of the run outputs: the volume, the bounding box, the holes
   and the advisory convention findings of every candidate.

```
uv run python evals/tmp/phase7_baseline/inspect_run.py
```

The configuration of the run is the `[agent]` section of the local, git-ignored
[`aturb.local.toml`](../aturb.local.toml):

```toml
[agent]
provider = "nvidia"
model = "nvidia/nemotron-3.5-super-vl-120b-a12b"
base_url = "https://integrate.api.nvidia.com/v1"
api_key_env = "NVIDIA_API_KEY"
max_input_tokens = 20000
max_output_tokens = 16000
max_cost_usd = 0.50
input_price_per_mtok = 0.0
output_price_per_mtok = 0.0
timeout_s = 300
```

The run wrote three dated files in the git-ignored folder
`evals/tmp/phase7_baseline`:
`evals/tmp/phase7_baseline/2026-11-23_064654.toml`
holds the result of the tasks,
`evals/tmp/phase7_baseline/2026-11-23_064654_agent.toml`
holds the record of the agent runs, and
`evals/tmp/phase7_baseline/2026-11-23_064654_attempts.toml`
holds the record of every attempt.

## A model call is not deterministic

A model call is not deterministic. The same prompt, the same model and the same
task can give a different answer on the next call, so this baseline is a
recorded measurement and not a function that can be replayed exactly. The
prompt versions, the token counts and the scores above describe this one run on
this date; a new run may score differently and may write a different candidate.
The implementation was not changed to make this run look better.

Four tasks are four tasks. This run is a measurement of one model on four
plates, and it does not claim that the agent has general mechanical engineering
autonomy: one of the four tasks passed, one was judged twice without a lift,
and two never produced a candidate that could be built.
