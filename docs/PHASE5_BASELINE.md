# Phase 5 baseline — one measured run of the stock agent

Date of the run: **2026-11-21**, 21:09 local time (Asia/Calcutta).
Task card: T5.13. Roadmap decision: D12.

This file is a record of one run. It is not a promise and not a target.

## What was run

- Task set: [`evals/tasks`](../evals/tasks) — one committed task folder,
  [`plate_2holes`](../evals/tasks/plate_2holes).
- Pack: `freecad`, the active pack of the local configuration.
- Provider: `nvidia` — NVIDIA-hosted, OpenAI-compatible Chat Completions.
- Model: `nvidia/nemotron-3.5-super-vl-120b-a12b`.
- Prompt version: `872c1e7cb85a7709` — the first sixteen hexadecimal characters
  of the SHA-256 of the exact prompt that was sent, as computed by
  [`prompt_version()`](../aturb/agent/prompt.py:58).
- Agent: one model call per task, one attempt, no retry and no repair loop.

**Qualification.** This baseline was measured under Phase 5 decision D7, which
put the expected values of `project/expect/` into the prompt.
[`docs/adr/0008-exclude-expectations-from-prompt.md`](adr/0008-exclude-expectations-from-prompt.md)
supersedes D7: the expectation file is no longer sent to the agent. The score of
0.60 and the prompt version `872c1e7cb85a7709` therefore describe the old
information boundary, and a run made after ADR-0008 is not directly comparable
to them without that qualification.

## The status and the score of every task

| Task           | Part      | Status   | Score | Required checks that passed          |
| -------------- | --------- | -------- | ----- | ------------------------------------ |
| `plate_2holes` | `plt0001` | `failed` | 0.6   | 3 of 5: `bbox_x`, `bbox_y`, `bbox_z` |

The required checks are the five named in
[`answer.toml`](../evals/tasks/plate_2holes/answer.toml:9); the score is
`max_score * passed / required`, so 3 of 5 gives 0.6.

Summary line of the run:

```
summary tasks=1 passed=0 failed=1 errored=0 score=0.6
```

## The token counts and the cost

| Task           | Input tokens | Output tokens | Total tokens | Cost (USD) |
| -------------- | ------------ | ------------- | ------------ | ---------- |
| `plate_2holes` | 1461         | 6918          | 8379         | 0.0        |

The cost is `0.0` because no price per million tokens is configured: the price
of the tokens of this provider is not known yet, as recorded under "Still
awaiting verification" in
[`docs/api_notes/model.md`](../docs/api_notes/model.md:70). The recorded cost is
the cost the configuration can compute, not a measured bill.

## The failure, exactly as it happened

The agent run itself succeeded: one call, one candidate file written, one
attempt, `status = "ok"`. The build of that candidate in FreeCAD succeeded too.
The task failed on the geometry checks.

Output of the run command:

```
task plate_2holes failed score=0.6
the checks did not pass: volume, hole_count
summary tasks=1 passed=0 failed=1 errored=0 score=0.6
```

The checks of the same candidate, measured with `aturb check`:

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

The expected values are the ones of
[`plt0001.toml`](../evals/tasks/plate_2holes/project/expect/plt0001.toml:15):
a volume of 35214.602 mm³ for the plate with its two holes, and two holes of
10 mm.

What the candidate did, in one line: it wrote a PartDesign body with a
rectangle sketch padded 5 mm, then a second sketch holding the two circles and
a `ThroughAll` pocket. The pocket cut no material, so the exported solid is the
plain 120 × 60 × 5 plate of 36000 mm³ with no hole in it.

The candidate file is not committed. It stays in the git-ignored scratch folder
as `evals/tmp/agent/plate_2holes/project/parts/plt0001_candidate.py`,
and the raw response of the model is not in this repository.

## The exact commands

1. The baseline run. The key is read from the local `.env` into the environment
   variable `NVIDIA_API_KEY`; the key is never printed and never enters the
   repository.

```
powershell -NoProfile -Command "$line = (Select-String -Path .env -Pattern '^NVIDIA_API_KEY=')[0].Line; $env:NVIDIA_API_KEY = $line.Substring(15).Trim(); uv run aturb eval evals/tasks --agent --config aturb.local.toml --results-dir evals/tmp/baseline"
```

2. The checks of the candidate, to record the failure in detail.

```
uv run aturb check evals/tmp/agent/plate_2holes/project plt0001 --config aturb.local.toml
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
`evals/tmp/baseline/2026-11-21_210901.toml` holds
the result of the task and
`evals/tmp/baseline/2026-11-21_210901_agent.toml`
holds the record of the agent run.

## A model call is not deterministic

A model call is not deterministic. The same prompt, the same model and the same
task can give a different answer on the next call, so this baseline is a
recorded measurement and not a function that can be replayed exactly. The
prompt version, the token counts and the score above describe this one run on
this date; a new run may score differently and may write a different candidate.
The implementation was not changed to make this run look better.
