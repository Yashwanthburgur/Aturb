# Phase 7.5 baseline — one measured run of the repair loop with the previous candidate

Date of the run: **2026-11-25**, 00:08 local time (Asia/Calcutta).
Task card: T7.5.2.

This file is a record of one run. It is not a promise and not a target.

## What was run

- Task set: [`evals/tasks`](../evals/tasks) — the four committed task folders
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

## The two differences from the Phase 7 baseline

The Phase 7 baseline is [`docs/PHASE7_BASELINE.md`](PHASE7_BASELINE.md). This
run differs from it in exactly two ways, and both are named here so that the
two sets of numbers are not read as the same measurement.

1. **The repair feedback carries the previous candidate.** The card T7.5.1 added
   the source code the agent wrote on the previous attempt to the repair block,
   as its last section, `Previous candidate:`, rendered by
   [`_previous()`](../aturb/agent/feedback.py:138) and passed by
   [`_repair_feedback()`](../aturb/agent/loop.py:242). The contract is
   [`docs/FEEDBACK.md`](FEEDBACK.md). The first attempt of a task is unchanged:
   it carries no repair block, so its prompt is still the Phase 6 prompt.
2. **The cumulative output budget was raised.** The local configuration sets
   `max_total_output_tokens = 48000`, where the Phase 7 run used the starting
   default of 24000. With a per-call cap of 16000 output tokens, the old
   cumulative cap refused the second and third attempt of a task before the
   model was called; the new cap does not. The per-call bounds are unchanged.

**The prompt version of the first attempt is the Phase 6 prompt version.** The
first prompt of a task is byte-identical to the prompt of the Phase 6 baseline,
so the two tasks that Phase 6 already ran carry the Phase 6 version, and the
two tasks that Phase 7 added carry a version of their own.

| Task           | Prompt version of attempt 1                       | Prompt version of attempt 2            |
| -------------- | ------------------------------------------------- | -------------------------------------- |
| `plate_2holes` | `25830ef6f36acf93` — the Phase 6 version          | —                                      |
| `plate_fillet` | `ca0607a60b7eacb6` — the Phase 6 version          | `0f3c75a86a1496cf` — the repair prompt |
| `plate_pocket` | `6780598d37967c98` — new task, no Phase 6 version | —                                      |
| `plate_step`   | `48dfb0d2194b33f7` — new task, no Phase 6 version | —                                      |

The repair prompt of `plate_fillet` is the only repair prompt of this run: the
repair block of [`docs/FEEDBACK.md`](FEEDBACK.md) with the `Previous candidate:`
section at its end. It carries no expected value of the task, as decided in
[`docs/adr/0008-exclude-expectations-from-prompt.md`](adr/0008-exclude-expectations-from-prompt.md),
and it has its own version, computed by
[`prompt_version()`](../aturb/agent/prompt.py:74).

**The bounds of the run.** The `[agent]` section of the local, git-ignored
[`aturb.local.toml`](../aturb.local.toml) sets the per-call bounds and the
cumulative output bound; the other cumulative bounds are the starting defaults
of [`DEFAULTS`](../aturb/agent/config.py:19).

| Bound                     | Value | Where it comes from              |
| ------------------------- | ----- | -------------------------------- |
| `max_attempts`            | 3     | starting default, not overridden |
| `max_input_tokens`        | 20000 | local configuration, per call    |
| `max_output_tokens`       | 16000 | local configuration, per call    |
| `max_cost_usd`            | 0.50  | local configuration, per call    |
| `max_total_input_tokens`  | 60000 | starting default, cumulative     |
| `max_total_output_tokens` | 48000 | local configuration, cumulative  |
| `max_total_cost_usd`      | 0.75  | starting default, cumulative     |
| `timeout_s`               | 300   | local configuration              |

## The status and the score of every task

| Task           | Part      | Attempt 1    | Final        | Attempts used      | Stop outcome  | Tokens in / out / total | Cost (USD) | Lift |
| -------------- | --------- | ------------ | ------------ | ------------------ | ------------- | ----------------------- | ---------- | ---- |
| `plate_2holes` | `plt0001` | `ok` 1.0     | `ok` 1.0     | 1 call, 1 record   | `passed`      | 2280 / 14338 / 16618    | 0.0        | 0.0  |
| `plate_fillet` | `plt0002` | `failed` 0.6 | `failed` 0.6 | 2 calls, 2 records | `model_error` | 2303 / 11882 / 14185    | 0.0        | 0.0  |
| `plate_pocket` | `plt0003` | `ok` 1.0     | `ok` 1.0     | 1 call, 1 record   | `passed`      | 2366 / 11407 / 13773    | 0.0        | 0.0  |
| `plate_step`   | `plt0004` | `error` 0.0  | `error` 0.0  | 1 call, 1 record   | `model_error` | 0 / 0 / 0               | 0.0        | 0.0  |

The lift is the score of the final attempt minus the score of attempt 1. It is
`0.0` for every task of this run: no task was lifted by the repair loop. The
score of a task is the score of the last judged candidate, so the failed model
call of the second attempt of `plate_fillet` leaves the score of its first
attempt as the score of the task. The required checks are the five named in
[`answer.toml`](../evals/tasks/plate_2holes/answer.toml:9) and in the three
other answer files; the score is `max_score * passed / required`, so 5 of 5
gives 1.0 and 3 of 5 gives 0.6.

Output of the run command:

```
task plate_2holes ok score=1.0
task plate_fillet failed score=0.6
the checks did not pass: volume, hole_count
task plate_pocket ok score=1.0
task plate_step error score=0.0
the model call failed: the nvidia model response has no generated text
summary tasks=4 passed=2 failed=1 errored=1 score=0.65
```

The summary score of the run is `0.65`, the mean of `1.0`, `0.6`, `1.0` and
`0.0`.

## The token counts and the cost

| Task           | Input tokens | Output tokens | Total tokens | Cost (USD) |
| -------------- | ------------ | ------------- | ------------ | ---------- |
| `plate_2holes` | 2280         | 14338         | 16618        | 0.0        |
| `plate_fillet` | 2303         | 11882         | 14185        | 0.0        |
| `plate_pocket` | 2366         | 11407         | 13773        | 0.0        |
| `plate_step`   | 0            | 0             | 0            | 0.0        |
| All four tasks | 6949         | 37627         | 44576        | 0.0        |

The cost is `0.0` because no price per million tokens is configured: the price
of the tokens of this provider is not known yet, as recorded under "Still
awaiting verification" in
[`docs/api_notes/model.md`](../docs/api_notes/model.md:80). The recorded cost is
the cost the configuration can compute, not a measured bill.

## The run, exactly as it happened

Two of the four tasks reached a passing candidate and two did not, so the
failures are written down here exactly as they happened.

**Every attempt of the run**, from
[`2026-11-25_000839_attempts.toml`](../evals/tmp/phase7_5_baseline/2026-11-25_000839_attempts.toml):

| Task           | Attempt | Prompt version     | In / out tokens | Status   | Outcome         | Score | Failed checks          |
| -------------- | ------- | ------------------ | --------------- | -------- | --------------- | ----- | ---------------------- |
| `plate_2holes` | 1       | `25830ef6f36acf93` | 2280 / 14338    | `ok`     | `passed`        | 1.0   | —                      |
| `plate_fillet` | 1       | `ca0607a60b7eacb6` | 2303 / 11882    | `failed` | `checks_failed` | 0.6   | `volume`, `hole_count` |
| `plate_fillet` | 2       | `0f3c75a86a1496cf` | 0 / 0           | `error`  | `model_error`   | 0.0   | —                      |
| `plate_pocket` | 1       | `6780598d37967c98` | 2366 / 11407    | `ok`     | `passed`        | 1.0   | —                      |
| `plate_step`   | 1       | `48dfb0d2194b33f7` | 0 / 0           | `error`  | `model_error`   | 0.0   | —                      |

The two attempts with no tokens are attempts in which the model call itself
failed: the provider answered without any generated text, and the error of the
file is `the model call failed: the nvidia model response has no generated
text`. No attempt of this run was refused before the model was called, so the
raised cumulative output budget was never the reason a task stopped.

**The geometry measured from the exported STEP files**, with
[`load_step()`](../aturb/verify/step.py:90) and
[`find_holes()`](../aturb/verify/holes.py:48):

| Part      | Volume (mm³)      | Bounding box (mm) | Solids | Holes                                            |
| --------- | ----------------- | ----------------- | ------ | ------------------------------------------------ |
| `plt0001` | 35214.60183660255 | 120 × 60 × 5      | 1      | 2 through holes of 10 mm at (−40, 0) and (40, 0) |
| `plt0002` | 35961.37166941154 | 120 × 60 × 5      | 1      | none                                             |
| `plt0003` | 67229.20367320512 | 120 × 60 × 10     | 1      | 2 through holes of 10 mm at (−40, 0) and (40, 0) |

`plt0004` has no candidate file and no STEP file: the model call failed before
anything was written.

The checks of the three candidates that were built, measured with `aturb check`.
The output of `plt0001` and of `plt0003` is the same eleven lines, all `passed`.
The output of `plt0002` is:

```
check volume failed: expected 35175.973506, got 35961.37166941154
check bbox_x passed
check bbox_y passed
check bbox_z passed
check hole_count failed: expected 2, got 0
check hole_diameter failed: the model holds no hole to measure
check hole_0 failed: the model holds fewer holes than expected
check hole_1 failed: the model holds fewer holes than expected
```

Five facts of this run are worth writing down, because they are what it measured:

- **The repair loop lifted nothing in this run.** The lift is `0.0` on all
  four tasks. The previous-candidate feedback was exercised exactly once, on
  the second attempt of `plate_fillet`, and that attempt failed at the model
  level before any candidate was written, so the loop stopped with the first
  attempt as the final judged candidate.
- **`plate_2holes` placed its holes correctly without a repair.** The candidate
  put the hole sketch on the top face of the plate, at `Z = THICKNESS_MM`, and
  cut with `Type = "ThroughAll"`, so the two holes went through the material:
  the measured solid is 35214.60183660255 mm³ with two holes of 10 mm at
  (−40, 0) and (40, 0), and the task passed on the first attempt. In the Phase 7
  run the same task put the sketch on the Z = 0 plane and cut no hole at all.
- **`plate_fillet` made the Z-placement mistake that `plate_2holes` made in
  Phase 7.** The candidate placed the holes sketch at Z = 0
  ([`plt0002_candidate.py`](../evals/tmp/agent/plate_fillet/project/parts/plt0002_candidate.py:58))
  and pocketed with `Type = "ThroughAll"`, so the cut went away from the
  material: the measured solid is a filleted plate of 35961.37166941154 mm³
  with no hole in it, against the expected 35175.973506 mm³ and two holes. The
  fillet was made with
  [`helper.corner_edges()`](../packs/freecad/helper/select.py:61) and
  [`helper.assert_count()`](../packs/freecad/helper/select.py:111), which
  selected and asserted and created nothing.
- **`plate_pocket` succeeded on the first attempt.** The empty-reasoning
  failure of the Phase 7 run did not recur. The candidate built the plate, the
  pocket and the two through-holes with Part primitives, and the measured
  volume is 67229.20367320512 mm³, the expected value of the task.
- **`plate_step` never produced a candidate.** The model call failed with
  `the nvidia model response has no generated text`, so the loop stopped at
  the model error and no repair prompt was ever sent on this task. The
  candidate of the Phase 7 run was cut off at the output cap instead; the
  failure moved, and the task still did not pass.

The conventions checker is advisory and never blocks a build.
[`check_conventions()`](../aturb/agent/conventions.py:65) reports one finding
for each of the three candidates that were written — `C2: line 12: the
parameter block is not at the top of the file` for `plt0001`, `C2: line 5: the
parameter block is not at the top of the file` for `plt0002` and `C2: line 8:
the parameter block is not at the top of the file` for `plt0003`. All three
candidates built and were judged; the findings are recorded as they were
measured, not as they should have been.

The candidate files are not committed. They stay in the git-ignored scratch
folder as
[`plt0001_candidate.py`](../evals/tmp/agent/plate_2holes/project/parts/plt0001_candidate.py),
[`plt0002_candidate.py`](../evals/tmp/agent/plate_fillet/project/parts/plt0002_candidate.py)
and [`plt0003_candidate.py`](../evals/tmp/agent/plate_pocket/project/parts/plt0003_candidate.py),
and the raw response of the model is not in this repository.

**The summary score of this run is not a measurement of the previous
candidate.** The Phase 7 run scored 0.4 and this run scored 0.65, but the two
tasks that passed here passed on their first attempt, before any repair
feedback existed, and the one task that needed a repair got a repair prompt
whose model call failed. The difference between 0.4 and 0.65 is the difference
between two runs of a model that is not deterministic, not the measured effect
of the previous candidate. The measured effect of the previous candidate in
this run is a lift of `0.0`.

## The exact commands

1. The baseline run. The key is read from the local `.env` into `NVIDIA_API_KEY`;
   it is never printed and never enters the repository.

```
powershell -NoProfile -Command "$line = Get-Content .env | Where-Object { $_ -match '^\s*NVIDIA_API_KEY\s*=' } | Select-Object -First 1; $env:NVIDIA_API_KEY = ($line -split '=',2)[1].Trim(); uv run aturb eval evals/tasks --agent --config aturb.local.toml --results-dir evals/tmp/phase7_5_baseline 2>&1 | Tee-Object -FilePath evals/tmp/phase7_5_baseline/live_run.log; exit $LASTEXITCODE"
```

2. The checks of the three candidates that were built.

```
uv run aturb check evals/tmp/agent/plate_2holes/project plt0001 --config aturb.local.toml
uv run aturb check evals/tmp/agent/plate_fillet/project plt0002 --config aturb.local.toml
uv run aturb check evals/tmp/agent/plate_pocket/project plt0003 --config aturb.local.toml
```

3. The inspection of the run outputs: the geometry and the convention findings.

```
uv run python evals/tmp/phase7_5_baseline/inspect_run.py
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
max_total_output_tokens = 48000
max_cost_usd = 0.50
input_price_per_mtok = 0.0
output_price_per_mtok = 0.0
timeout_s = 300
```

The run wrote three dated files in the git-ignored folder
[`evals/tmp/phase7_5_baseline`](../evals/tmp/phase7_5_baseline):
[`2026-11-25_000839.toml`](../evals/tmp/phase7_5_baseline/2026-11-25_000839.toml)
(the results),
[`2026-11-25_000839_agent.toml`](../evals/tmp/phase7_5_baseline/2026-11-25_000839_agent.toml)
(the agent runs) and
[`2026-11-25_000839_attempts.toml`](../evals/tmp/phase7_5_baseline/2026-11-25_000839_attempts.toml)
(every attempt).

## A model call is not deterministic

A model call is not deterministic. The same prompt, the same model and the same
task can give a different answer on the next call, so this baseline is a
recorded measurement and not a function that can be replayed exactly. The
prompt versions, the token counts and the scores above describe this one run on
this date; a new run may score differently and may write a different candidate.

Four tasks are four tasks. This run is a measurement of one model on four
plates, and it does not claim that the agent has general mechanical engineering
autonomy: two of the four tasks passed on the first attempt, one was judged
twice without a lift, and one never produced a candidate at all. The repair
loop with the previous candidate is bounded, and this run shows that it lifted
nothing on these four tasks.
