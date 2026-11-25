# Phase 8 roadmap — expectation-free arbitrary-prompt generation

Phase 8 adds a user-facing `aturb generate` path beside the fixed-task evaluator.
It follows the architecture ([`docs/ARCHITECTURE.md`](ARCHITECTURE.md)), the
code-first and runner decisions, the candidate-only feedback boundary and the
bounded loop of ADR-0001 through ADR-0009. Its new architectural decision is
[`docs/adr/0010-arbitrary-prompt-generation.md`](adr/0010-arbitrary-prompt-generation.md).

Scope: one thing — turn an arbitrary engineering requirement into editable
source and build artifacts without creating evaluation inputs or claiming a
correctness score. The work is split into the cards in
[`docs/PHASE8_TASKS.md`](PHASE8_TASKS.md).

## Current state after Phase 7.5

- The agent writes one candidate source file through the active pack.
- The evaluator requires a task folder, an answer file and expectations, then
  judges and scores the exported STEP.
- The bounded loop reuses one attempt primitive, cumulative budgets and
  candidate-only repair feedback.
- The prompt excludes evaluator expectations, and the previous candidate can be
  carried into a repair prompt verbatim.
- The pack prompt records verified backend guidance; the core treats it as
  opaque text and remains CAD-neutral.
- No user-facing path exists for a requirement that has no task identity,
  answer specification or expected measurements.

## Objective

Accept a requirement directly from a positional prompt or a prompt file, build
it through the active pack, repair candidate-side failures within fixed bounds,
and leave a portable output workspace. Success means that the current attempt
produced readable, valid, single-solid STEP geometry. It does not mean that an
evaluator certified the engineering intent.

## Decisions

**D1 — Generation is separate from evaluation.** The new service never creates
`task.toml`, `answer.toml` or `project/expect/`, never calls `judge_task()` or
`score_task()`, and never emits a score. The existing evaluation commands and
records remain unchanged.

**D2 — The existing seams are reused.** `PreparedTask` and `run_attempt()` own
prompt composition, per-call limits, the model call and candidate writing.
`BuildRequest` remains the only build door. `load_step()` and
`summarize_geometry()` provide neutral measurements. `BuildFeedback` and
`feedback_text()` remain frozen.

**D3 — The workspace is standalone.** The output root contains `project/parts/`
for editable candidate source and `project/out/` for build products. No
requirement fixture, answer, expectation or reference candidate is copied into
it. The requirement lives in the prompt, not in an evaluation task file.

**D4 — Every build starts with a clean artifact directory.** Immediately before
each runner call, `project/out/<part_id>` is deleted and recreated. A later
missing, broken or failed build therefore cannot accept an earlier STEP or
native file.

**D5 — Geometry outcomes have explicit meanings.** A readable valid single solid
finishes with `status = "ok"` and `stop_reason = "built"`. A failed build, a
missing STEP and an unreadable STEP map to their existing failure kinds. A
readable invalid or multi-solid model keeps `Build: ok` in repair feedback,
adds the candidate-only error note and retains its measured geometry.

**D6 — The loop is bounded.** The configured attempt limit and cumulative token
and cost caps apply across the whole generation. Budget refusal happens before
the model call that would pass a cap. `runner_crash` and `input_error` are
unrepairable; model errors stop immediately. No hidden retry exists.

**D7 — The result is a portable engineering record.** `result.toml` sits at the
workspace root. Source, STEP and native paths are relative to that root. The
manifest records status, stop reason, attempts, usage, prompt version, build
outcome, advisory findings and measured geometry, never an absolute path or a
score.

**D8 — The CLI is thin.** The handler resolves prompt input, configuration,
pack, runner and model client, then calls the service. It prints a human-readable
report and returns 0 for a built result, 1 for an unsuccessful generation and 2
for input, configuration or credential errors. Existing commands keep their
text and exit codes.

**D9 — Verification uses canned model answers.** Offline tests use fake clients
and the stub pack. The real-backend test uses a canned sequence with a broken
first candidate and a valid second candidate. Neither path makes a network or
live-model call.

**D10 — Live verification is a separate later card.** T8.05 runs the interactive
command with the configured model only after the implementation cards are
reviewed. Its output is a recorded run, not a deterministic test or a general
engineering-autonomy claim.

## Generation sequence

1. Validate the requirement, part identity and configured bounds.
2. Read the active pack prompt and prepare the standalone workspace.
3. Compose the prompt and refuse the call if a cumulative cap would be passed.
4. Run one model attempt and write its candidate source.
5. Clear the part's output directory and build through the runner.
6. Inspect only the current attempt's STEP and measure its candidate geometry.
7. Finish on a valid single solid; otherwise stop on a deterministic bound or
   carry candidate-only feedback into the next attempt.
8. Write `result.toml` and print the engineering report.

## Stop reasons

| Stop reason         | Meaning                                                    |
| ------------------- | ---------------------------------------------------------- |
| `built`             | the current attempt exported a readable valid single solid |
| `max_attempts`      | the final permitted candidate still needs repair           |
| `budget_exceeded`   | the next call would pass a cumulative cap                  |
| `unrepairable`      | the runner or request failed in a way a rewrite cannot fix |
| `model_error`       | the model call, answer or candidate write failed           |
| `settings_error`    | input or configured bounds are invalid                     |
| `preparation_error` | the prompt or workspace could not be prepared              |

## Output contract

| Output                                         | Condition                                              |
| ---------------------------------------------- | ------------------------------------------------------ |
| `project/parts/<part_id>_candidate<extension>` | a candidate was written                                |
| `project/out/<part_id>/`                       | the current attempt's build products only              |
| exported STEP                                  | the current attempt produced it                        |
| native artifact                                | the active pack produced it                            |
| `result.toml`                                  | every completed command, including unsuccessful builds |

All manifest paths are relative to the workspace. Geometry fields are present
only when STEP was readable and measured. Convention findings are advisory and
never independently refuse a build.

## Evaluation strategy

- Unit tests prove input validation, cumulative budgets, stop conditions,
  feedback content, token accounting and per-attempt artifact isolation.
- Offline command tests prove prompt and prompt-file input, exit codes, manifest
  parsing, relative paths and human-readable reporting.
- A real-backend test proves a two-attempt repair and measures the exported
  geometry without a live model.
- The full existing suite proves that evaluation and runner contracts did not
  move.
- T8.05 later records one interactive live-model run with its configuration,
  prompt versions, attempts, stop reason and measured output.

## Dependencies and task sequence

T8.01 → T8.02 → T8.03 → T8.04 → T8.05

T8.01 fixes the architecture and cards. T8.02 implements the service, T8.03 the
handler and manifest, and T8.04 the command registration and end-to-end proof.
T8.05 is intentionally deferred until those cards pass their gates.

## Acceptance criteria

- Arbitrary requirements generate source and current-attempt artifacts without
  any evaluation fixture or correctness score.
- A stale artifact cannot survive into a later build or be accepted as its
  output.
- Every repair prompt contains candidate-side information only, including
  measured invalid or multi-solid geometry when readable.
- The manifest is valid TOML with relative paths and the report exposes measured
  facts, usage, artifacts and errors.
- Existing commands, records, scoring and the eight failure kinds are unchanged.
- Offline and real-backend tests, lint, file-size and agnosticism gates pass.
- No implementation test makes a live-model or network call.

## Scope boundaries and exclusions

Phase 8 does not introduce a runner contract change, a ninth failure kind, an
answer or result schema change, a geometry DSL, an intermediate representation,
an operations layer, a ReAct framework, autonomous tool calling, multi-agent
logic, a GUI, a viewer or a new external dependency. It does not modify the
committed task set or the frozen evaluation pipeline.

## Architectural risks

| Risk                                  | Consequence                         | Control                                                   |
| ------------------------------------- | ----------------------------------- | --------------------------------------------------------- |
| stale artifact accepted as new output | false success                       | delete the part output before every build                 |
| generation becomes hidden evaluation  | fabricated targets and scores       | no task, answer, expectation, judge or scoring call       |
| invalid geometry cannot be repaired   | repeated identical failure          | retain candidate geometry in the existing feedback block  |
| unbounded model spend                 | unreliable operation                | attempt and cumulative budget checks before every call    |
| manifest ties output to one machine   | downstream tools cannot relocate it | relative paths only                                       |
| CLI growth breaks existing behavior   | regression in established commands  | thin handler and unchanged dispatch for existing commands |

## Relationship to Phase 9

A later read-only viewer may consume `result.toml` and the exported STEP from a
client outside the CAD-neutral core. Phase 8 supplies the portable manifest but
does not implement a server, browser interface, geometry conversion pipeline or
GUI.
