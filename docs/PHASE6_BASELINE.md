# Phase 6 baseline — one measured run of the agent with the conventions and the helper

Date of the run: **2026-11-22**, 14:30 local time (Asia/Calcutta).
Task card: T6.11.

This file is a record of one run. It is not a promise and not a target.

## What was run

- Task set: [`evals/tasks`](../evals/tasks) — two committed task folders,
  [`plate_2holes`](../evals/tasks/plate_2holes) and
  [`plate_fillet`](../evals/tasks/plate_fillet).
- Pack: `freecad`, the active pack of the local configuration.
- Provider: `nvidia` — NVIDIA-hosted, OpenAI-compatible Chat Completions.
- Model: `nvidia/nemotron-3.5-super-vl-120b-a12b`.
- Prompt version: one per task, because the requirement of each task is part of
  the prompt — `25830ef6f36acf93` for `plate_2holes` and `ca0607a60b7eacb6` for
  `plate_fillet`. Each is the first sixteen hexadecimal characters of the
  SHA-256 of the exact prompt that was sent, as computed by
  [`prompt_version()`](../aturb/agent/prompt.py:63).
- Agent: one model call per task, one attempt, no retry and no repair loop.
- The run was made once. Nothing in the implementation was changed before or
  after it to make the result look better.

**Qualification.** The prompt version differs from the Phase 5 baseline
(`872c1e7cb85a7709`), because the project conventions were added to the prompt
in Phase 6, and because the second task brings a second requirement and so a
second prompt. The Phase 5 score of 0.60 was also measured under Phase 5
decision D7, which put the expected values of
[`project/expect/`](../evals/tasks/plate_2holes/project/expect) into the prompt.
[`docs/adr/0008-exclude-expectations-from-prompt.md`](adr/0008-exclude-expectations-from-prompt.md)
supersedes D7: the expectation file is no longer sent to the agent. The two
baselines therefore describe two different information boundaries and are not
directly comparable without that qualification.

## The status and the score of every task

| Task           | Part      | Status | Score | Required checks that passed                                  |
| -------------- | --------- | ------ | ----- | ------------------------------------------------------------ |
| `plate_2holes` | `plt0001` | `ok`   | 1.0   | 5 of 5: `volume`, `bbox_x`, `bbox_y`, `bbox_z`, `hole_count` |
| `plate_fillet` | `plt0002` | `ok`   | 1.0   | 5 of 5: `volume`, `bbox_x`, `bbox_y`, `bbox_z`, `hole_count` |

The required checks are the five named in
[`answer.toml`](../evals/tasks/plate_2holes/answer.toml:9) and in
[`answer.toml`](../evals/tasks/plate_fillet/answer.toml:9); the score is
`max_score * passed / required`, so 5 of 5 gives 1.0.

Output of the run command:

```
task plate_2holes ok score=1.0
task plate_fillet ok score=1.0
summary tasks=2 passed=2 failed=0 errored=0 score=1.0
```

## The token counts and the cost

| Task           | Input tokens | Output tokens | Total tokens | Cost (USD) |
| -------------- | ------------ | ------------- | ------------ | ---------- |
| `plate_2holes` | 2280         | 3835          | 6115         | 0.0        |
| `plate_fillet` | 2303         | 5023          | 7326         | 0.0        |
| Both tasks     | 4583         | 8858          | 13441        | 0.0        |

The cost is `0.0` because no price per million tokens is configured: the price
of the tokens of this provider is not known yet, as recorded under "Still
awaiting verification" in
[`docs/api_notes/model.md`](../docs/api_notes/model.md:80). The recorded cost is
the cost the configuration can compute, not a measured bill.

## The run, exactly as it happened

No task failed and no task errored, so there is no failure to write down. The
run is recorded here as it was measured.

The agent run of each task succeeded: one call, one candidate file written, one
attempt, `status = "ok"` in
`evals/tmp/baseline/2026-11-22_143053_agent.toml`.
The build of each candidate in FreeCAD 1.0.1 succeeded too, and the exported
STEP file was read back with build123d.

The geometry measured from the two exported STEP files:

| Part      | Volume (mm³)      | Bounding box (mm) | Faces | Solids | Valid | Holes                                            |
| --------- | ----------------- | ----------------- | ----- | ------ | ----- | ------------------------------------------------ |
| `plt0001` | 35214.60183660255 | 120 × 60 × 5      | 8     | 1      | yes   | 2 through holes of 10 mm at (−40, 0) and (40, 0) |
| `plt0002` | 35175.9735060141  | 120 × 60 × 5      | 12    | 1      | yes   | 2 through holes of 10 mm at (−40, 0) and (40, 0) |

The volumes and the bounding boxes were read with
[`load_step()`](../aturb/verify/step.py:90) and the holes with
[`find_holes()`](../aturb/verify/holes.py:48).

The checks of the same two candidates, measured with `aturb check`:

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

All eleven checks passed for each of the two candidates.

Three facts of this run are worth writing down, because they are what the
Phase 6 work was for:

- The Phase 5 failure did not recur. In Phase 5 the pocket cut no material and
  the exported solid was a plain plate of 36000 mm³ with no hole in it. The
  candidate of this run cut both holes: the measured volume is
  35214.60183660255 mm³ and the model holds two holes of 10 mm.
- The candidate of `plate_fillet` selected the fillet edges with the helper,
  with [`helper.corner_edges()`](../packs/freecad/helper/select.py:61) and
  [`helper.assert_count()`](../packs/freecad/helper/select.py:111), and created
  the `PartDesign::Fillet` feature of
  `evals/tmp/agent/plate_fillet/project/parts/plt0002_candidate.py`
  itself. The helper selected and asserted; it created nothing. The
  twelve faces of the measured solid are the four fillet faces added to the
  eight faces of the plain plate.
- The conventions checker is advisory and never blocks a build.
  [`check_conventions()`](../aturb/agent/conventions.py:65) reports no finding
  for the candidate of `plate_2holes`, and one finding for the candidate of
  `plate_fillet`: `C2: line 8: the parameter block is not at the top of the
file`. The task still scored 1.0. The finding is recorded here as it was
  measured, not as it should have been.

The candidate files are not committed. They stay in the git-ignored scratch
folder as
`evals/tmp/agent/plate_2holes/project/parts/plt0001_candidate.py`
and
`evals/tmp/agent/plate_fillet/project/parts/plt0002_candidate.py`,
and the raw response of the model is not in this repository.

## The exact commands

1. The baseline run. The key is read from the local `.env` into the environment
   variable `NVIDIA_API_KEY`; the key is never printed and never enters the
   repository.

```
powershell -NoProfile -Command "$line = (Select-String -Path .env -Pattern '^NVIDIA_API_KEY=')[0].Line; $env:NVIDIA_API_KEY = $line.Substring(15).Trim(); uv run aturb eval evals/tasks --agent --config aturb.local.toml --results-dir evals/tmp/baseline"
```

2. The checks of the two candidates, to record the geometry in detail.

```
uv run aturb check evals/tmp/agent/plate_2holes/project plt0001 --config aturb.local.toml
uv run aturb check evals/tmp/agent/plate_fillet/project plt0002 --config aturb.local.toml
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

The run wrote two dated files in the git-ignored folder
`evals/tmp/baseline`:
`evals/tmp/baseline/2026-11-22_143053.toml` holds
the result of the tasks and
`evals/tmp/baseline/2026-11-22_143053_agent.toml`
holds the record of the agent runs.

## A model call is not deterministic

A model call is not deterministic. The same prompt, the same model and the same
task can give a different answer on the next call, so this baseline is a
recorded measurement and not a function that can be replayed exactly. The
prompt versions, the token counts and the scores above describe this one run on
this date; a new run may score differently and may write a different candidate.
The implementation was not changed to make this run look better.
