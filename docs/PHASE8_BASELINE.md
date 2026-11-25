# Phase 8 baseline — one live arbitrary-prompt generation through `aturb generate`

Date of the run: **2026-11-25**, 09:55 local time (Asia/Calcutta).
Task card: T8.05.
Commit of the run: `d84c18e` — `feat(cli): wire aturb generate command and end-to-end tests`.

This file is a record of one run. It is not a promise and not a target.

## What was run

- Command: `aturb generate` with one positional requirement and the local
  configuration named with `--config`, from the root of the repository, with the
  active pack of that configuration and the configured provider.
- Pack: `freecad`, the active pack of the local configuration, FreeCAD 1.0.1
  (libs 1.0.1R39285, Git).
- Provider: `nvidia` — NVIDIA-hosted, OpenAI-compatible Chat Completions.
- Model: `nvidia/nemotron-3.5-super-vl-120b-a12b`.
- Output workspace: `evals/tmp/generate/2026-11-25_095531` — the dated default
  output root of the command, so no `--out` was given.
- Part identity: `part0001` — the starting default of
  [`DEFAULT_PART_ID`](../aturb/agent/generate.py:27), so no `--part-id` was given.
- The run was made once. Nothing was changed before or after it to make the
  result look better, and no attempt was repeated or discarded.

The command was:

```
uv run aturb generate "Build a 100 x 50 x 8 mm rectangular mounting plate centred on the origin (Z=0 to Z=8) with four 6 mm through-holes at (±40, ±15) mm and a 5 mm fillet on the four vertical outer corners." --config aturb.local.toml
```

The configuration was named explicitly with `--config aturb.local.toml`. The API
key is not in the configuration file; the configuration names the environment
variable `NVIDIA_API_KEY`, and the key was read from the local, git-ignored
`.env` into that variable. The key was never printed and never entered the
repository.

## The requirement and the prompt

The requirement was one positional argument of the command:

```
Build a 100 x 50 x 8 mm rectangular mounting plate centred on the origin (Z=0 to Z=8) with four 6 mm through-holes at (±40, ±15) mm and a 5 mm fillet on the four vertical outer corners.
```

The prompt that was sent to the model is the five fixed sections of
[`compose_prompt()`](../aturb/agent/prompt.py:43) — the core instruction, the
pack prompt of `packs/freecad/prompt/agent.md`, the project conventions, the
requirement and the output contract — and its version is
`b11fc29e0ec19a76`, the first sixteen hexadecimal characters of the SHA-256 of
the exact prompt text, computed by
[`prompt_version()`](../aturb/agent/prompt.py:74).

**The requirement is proven by that hash.** Composing the prompt from the pack
prompt of commit `d84c18e` and the requirement above reproduces the recorded
version `b11fc29e0ec19a76` exactly, so this is the requirement the run used
and not a reconstruction of it.

The prompt carried no expected value of any kind. There was no task, no answer
and no expectation to exclude, because the generation path never reads one.

## The bounds of the run

The `[agent]` section of the local, git-ignored
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
| `timeout_s`               | 300   | local configuration, model call  |
| `build_s`                 | 60    | local configuration, build call  |

The run used one attempt of the three it was allowed, so no bound was reached
and no budget refusal happened.

## The measured results

| Field                        | Value                                               |
| ---------------------------- | --------------------------------------------------- |
| Status                       | `ok`                                                |
| Stop reason                  | `built`                                             |
| Attempts                     | 1                                                   |
| Prompt version               | `b11fc29e0ec19a76`                                  |
| Build status                 | `ok`                                                |
| Failure kind                 | none                                                |
| Input tokens                 | 2312                                                |
| Output tokens                | 9305                                                |
| Total tokens                 | 11617                                               |
| Cost (USD)                   | 0.0                                                 |
| `is_valid`                   | `true`                                              |
| `is_single_solid`            | `true`                                              |
| Volume                       | 38923.539846484084 mm³                              |
| Bounding box                 | 100 x 50 x 8 mm                                     |
| Holes                        | 4 through holes of 6 mm                             |
| Hole positions               | (±40, ±15) mm                                       |
| Advisory convention findings | none                                                |
| Helper use                   | `helper.corner_edges()` and `helper.assert_count()` |
| `task.toml` created          | none                                                |
| `answer.toml` created        | none                                                |
| `expect/` created            | none                                                |

The cost is `0.0` because no price per million tokens is configured: the local
configuration sets `input_price_per_mtok = 0.0` and
`output_price_per_mtok = 0.0`, so
[`compute_cost_usd()`](../aturb/agent/run.py:224) returns `0.0` for every call.
**This is not a measured bill and it does not mean that the provider call was
free.** The price of the tokens of this provider is still unknown, as recorded
under "Still awaiting verification" in
[`docs/api_notes/model.md`](../docs/api_notes/model.md:70).

## The console report

The report is a pure function of the result, so the manifest of the run is
enough to rebuild it. The lines below are the lines the run printed, rebuilt
with the formatter of commit `d84c18e`:

```
Status: ok
Stop reason: built
Part: part0001
Attempts: 1
Tokens: 2312 in / 9305 out
Cost (USD): 0.000000
Prompt version: b11fc29e0ec19a76
Build: ok
Saved files:
  source: project/parts/part0001_candidate.py
  STEP: project/out/part0001/part0001.step
  native: project/out/part0001/part0001.FCStd
  manifest: result.toml
Measured geometry:
  is_valid: true
  is_single_solid: true
  volume: 38923.539846 mm^3
  bbox_size: 100 x 50 x 8 mm
  holes: 4
    hole 1: diameter 6 mm, position (-40, -15) mm
    hole 2: diameter 6 mm, position (-40, 15) mm
    hole 3: diameter 6 mm, position (40, -15) mm
    hole 4: diameter 6 mm, position (40, 15) mm
```

T8.05 adds one line to that report, the workspace path, so the same run now
prints `Workspace: evals/tmp/generate/2026-11-25_095531` above `Saved files:`.
The line is written by [`format_generate_report()`](../aturb/agent/generate_cli.py:69)
and is relative to the current working directory when the workspace is inside
it. The manifest is unchanged by T8.05: it still holds relative paths only.

## The manifest

The manifest of the run, `result.toml` at the root of the workspace, in full:

```toml
status = "ok"
part_id = "part0001"
stop_reason = "built"
attempts = 1
input_tokens = 2312
output_tokens = 9305
cost_usd = 0.0
prompt_version = "b11fc29e0ec19a76"
build_status = "ok"
failure_kind = ""
error = ""
conventions = []
part_file = "project/parts/part0001_candidate.py"
step_file = "project/out/part0001/part0001.step"
native_file = "project/out/part0001/part0001.FCStd"
is_valid = true
is_single_solid = true
volume = 38923.539846484084
bbox_size = [100.0, 50.0, 8.0]
hole_count = 4
holes = [{ diameter = 6.0, x = -40.0, y = -15.0 }, { diameter = 6.0, x = -40.0, y = 15.0 }, { diameter = 6.0, x = 40.0, y = -15.0 }, { diameter = 6.0, x = 40.0, y = 15.0 }]
```

Every path in it is relative to the workspace root. The manifest holds no
absolute path, no answer, no expectation and no score.

## The independent verification of the STEP file

The manifest was not trusted. The exported STEP file was read again with
[`load_step()`](../aturb/verify/step.py:90) and the holes were found again with
[`find_holes()`](../aturb/verify/holes.py:48):

| Measurement       | Value                                         |
| ----------------- | --------------------------------------------- |
| `is_valid`        | `True`                                        |
| `is_single_solid` | `True`                                        |
| Solids            | 1                                             |
| Volume            | 38923.539846484084 mm³                        |
| Surface area      | 12665.398163397442 mm²                        |
| Bounding box      | 100 x 50 x 8 mm                               |
| Holes             | 4, every one of them through                  |
| Hole diameters    | 6.0 mm                                        |
| Hole positions    | (−40, −15), (−40, 15), (40, −15), (40, 15) mm |
| Hole axis height  | 4.0 mm, the middle of the 8 mm plate          |

The independent measurement agrees with the manifest to the last digit of the
volume.

## The hand calculation

The volume of the part was also computed by hand, without the CAD and without
the STEP file:

```
plate                 100 * 50 * 8                = 40000
four 6 mm holes       4 * (pi * 3^2 * 8)          = 904.7786842338604
four 5 mm fillets     4 * (25 - 6.25 * pi) * 8    = 171.68146928204135
expected volume       40000 - 904.7786842338604 - 171.68146928204135
                                                     = 38923.5398464841
```

The measured volume is 38923.539846484084 mm³ and the hand calculation is
38923.5398464841 mm³. The difference is −1.46 × 10⁻¹¹ mm³, which is the
floating-point noise of the two computations and not a geometric difference.
The fillet term is the area a 5 mm fillet removes from one corner of the
100 x 50 rectangle, `(5² − π·5²/4) = 25 − 6.25π`, times the 8 mm thickness,
times four corners.

## The advisory conventions

[`check_conventions()`](../aturb/agent/conventions.py:65) was run again over
the candidate source of the run and reported **no findings**, and the manifest
records the same empty list. The candidate puts its parameter block at the top
of the file, names every dimension in millimetres and keeps the machine values
in that block, so the three advisory checks of the project conventions found
nothing to report. The conventions checker is advisory and never blocks a
build: an empty finding list is not a correctness claim.

## The helper boundary

The candidate used the pack helper for the four corner fillets, and only for
that: [`helper.corner_edges()`](../packs/freecad/helper/select.py:61) selected
the four vertical outer corner edges of the padded plate, and
[`helper.assert_count()`](../packs/freecad/helper/select.py:111) asserted that
exactly four such edges were found.

Both helpers select and assert. Neither creates a feature: the fillet itself is
a `PartDesign::Fillet` feature of the candidate, and the four holes are
`PartDesign::Pocket` features of the candidate. The helper boundary of
[`docs/adr/0007-selection-rule-and-helper-boundary.md`](../docs/adr/0007-selection-rule-and-helper-boundary.md)
held in this run.

The candidate also placed the hole sketches on the top face of the plate, at
`Z = THICKNESS_MM`, and cut them with `Type = "ThroughAll"`, so the default
`-Z` cut entered the material. The four holes are through holes, as the
independent measurement above shows. This is the placement that the Phase 7.5
baseline recorded as the difference between a cut hole and no hole at all.

## No evaluation fixture was created

The workspace of the run holds only the candidate source, the build outputs and
the manifest: `result.toml`, `project/parts/part0001_candidate.py` and the five
files of `project/out/part0001/` — `build.log`, `job.json`, `part0001.FCStd`,
`part0001.step` and `result.json`.

There is no `task.toml`, no `answer.toml` and no `expect/` folder anywhere in
the workspace, and the committed task set under `evals/tasks` was not touched.
The generation path never calls the judge and never reports a score, as
decided in
[`docs/adr/0010-arbitrary-prompt-generation.md`](../docs/adr/0010-arbitrary-prompt-generation.md).

The candidate files are not committed. They stay in the git-ignored scratch
folder, and the raw response of the model is not in this repository.

## The two qualifications

**One run is not a benchmark, and a model call is not deterministic.** A model
call is not deterministic: the same prompt, the same model and the same
requirement can give a different answer on the next call, so this baseline is
a recorded measurement and not a function that can be replayed exactly. The
prompt version, the token counts and the geometry above describe this one run
on this date; a new run may build a different candidate, may need more than
one attempt and may fail. One successful run is one run: it does not claim that
the agent has general mechanical engineering autonomy, it does not measure the
success rate of the path, and it does not claim that the part satisfies an
engineering target, because no target was supplied. The repair loop was not
exercised either: the run stopped on the first attempt, so no repair prompt was
sent and no feedback was rendered. The fixed task set of `evals/tasks` and its
independent expectations remain the way to measure agent performance.

**The cost of `0.0` is a configuration fact, not a free call.** The recorded
cost is `0.0` because the local configuration sets
`input_price_per_mtok = 0.0` and `output_price_per_mtok = 0.0`. The provider
call was a real call to a hosted model and was not free; the price of its
tokens is simply not configured yet, so the configuration cannot compute it.
Any figure derived from this baseline must treat the cost as unknown, not as
zero.
