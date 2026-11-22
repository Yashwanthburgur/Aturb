# Phase 7 task roadmap — the bounded improvement loop

Proposed task cards for Phase 7, derived from the Phase 6 roadmap
([`docs/PHASE6_ROADMAP.md`](PHASE6_ROADMAP.md)), the architecture
([`docs/ARCHITECTURE.md`](ARCHITECTURE.md)), the decision records
([`docs/adr/`](adr/README.md)) and the Phase 6 baseline
([`docs/PHASE6_BASELINE.md`](PHASE6_BASELINE.md)).

Scope: one thing — a bounded, measured repair loop. The agent writes a part
file, the pack builds it, the neutral checks judge the exported STEP, and when
the judgement is not good enough the agent is told **what its own candidate
measures** and writes the file again. The loop is bounded by an attempt limit
and a budget, it stops on deterministic conditions, and every attempt is
recorded.

The agent still writes CAD code. The loop adds no tool, no operation and no
intermediate language: it only decides whether to ask the model for another
attempt, and what to tell it.

## Current state after Phase 6

- The agent path is one task, one model call, one candidate file, one build and
  one score: [`run_agent()`](../aturb/agent/run.py:40) writes the candidate and
  [`run_task()`](../aturb/evals/runner.py:40) builds and scores it.
- The prompt has five sections — core instruction, pack prompt, project
  conventions, requirement, output contract — and is named by the hash of its
  text ([`compose_prompt()`](../aturb/agent/prompt.py:38)).
- The expected values of the part are **not** in the prompt
  ([`docs/adr/0008-exclude-expectations-from-prompt.md`](adr/0008-exclude-expectations-from-prompt.md)).
- The Phase 6 baseline scored 1.0 on both committed tasks with one attempt each
  ([`docs/PHASE6_BASELINE.md`](PHASE6_BASELINE.md)); the Phase 5 baseline scored
  0.60 on one task, and the failure was a part file that built but cut no material.
- The agent-run record has eleven fields and says what the agent did, not what
  the geometry scored ([`AgentRun`](../aturb/agent/types.py:63)).

## The problem this phase solves

The Phase 5 baseline showed a failure the agent could not see: it wrote code
that looked right and did nothing. The Phase 6 work gave the agent the
conventions and a way to select geometry, and the Phase 6 baseline then scored
1.0 — but on two tasks a single shot already solved. **The current task set
cannot show whether a repair loop helps**, because there is nothing to repair.

Phase 7 therefore has two deliverables that can be measured separately:

1. a bounded repair loop, with a feedback contract that tells the agent only
   what its own candidate measures, and never what the evaluator knows;
2. a task set with parts that a single shot can get wrong, so the lift of
   attempt 1 against the final attempt is a measured number and not a claim.

## Decisions

**D1 — The loop is bounded and lives in the agent layer.** The loop is a new
module in [`aturb/agent/`](../aturb/agent/), not in the evaluator and not in a
pack. It is bounded by an explicit attempt limit and by cumulative token and
cost caps. There is no unbounded loop, no ReAct framework, no autonomous tool
calling and no multi-agent logic.

**D2 — The evaluator stays the judge and the only reader of the expectation
file.** The agent layer never reads `project/expect/`. The evaluator reads it
and judges the candidate; nothing it learns crosses into the agent layer. The
scratch workspace keeps `project/expect/`, as ADR-0008 requires, and the agent
path still never opens it.

**D3 — The feedback contract.** The repair prompt may carry:

- the build status and the failure kind;
- the sanitized build error text and the sanitized traceback;
- the CAD's own informational diagnostics, which ADR-0005 already calls hints
  and never a verdict;
- the advisory convention findings of the candidate file, from
  [`check_conventions()`](../aturb/agent/conventions.py:65);
- an independent candidate-only geometry summary, measured from the exported
  STEP of the candidate when the build status is `ok`: `is_valid`,
  `is_single_solid`, the measured volume, the bounding-box size and the
  detected holes with their count, diameters and positions.

It must never carry:

- the expected value, the tolerance, the name, the verdict or the failure
  message of any evaluator check, and the score of the task;
- the answer file, the answer spec or the contents of `project/expect/`;
- the text, the path or the file name of the expectation file;
- a raw [`CheckResult`](../aturb/verify/result.py:20) or any evaluator-side object.

**D4 — The leak is prevented by the type, not by a convention.** There is no
safe view of a check, because every field of a check result is evaluator-side:
the name, the verdict, the expected value, the tolerance and the message all
come from the expectation file. The type that crosses the boundary is instead
a **candidate-only geometry summary**, measured from the exported STEP of the
candidate alone with [`load_step()`](../aturb/verify/step.py:90) and
[`find_holes()`](../aturb/verify/holes.py:48). The feedback formatter takes
that summary, the build outcome, the diagnostics and the convention findings,
and it has no parameter that could carry an expectation file path, an
expectation dictionary or an answer spec.

**D5 — Attempt 1 is byte-identical to the Phase 6 prompt.** The repair prompt
is the five-section prompt plus one section, and the section is empty when
there is no feedback. So the first attempt of a Phase 7 run sends exactly the
Phase 6 prompt, the Phase 6 baseline stays comparable, and `max_attempts = 1`
reproduces the single-shot path exactly.

**D6 — The agent-run record keeps its eleven fields.** The record of
[`aturb/agent/record.py`](../aturb/agent/record.py:27) does not grow, so every
reader of it keeps working. Three fields change meaning, and only in the
direction of more information:

| Field                                       | Phase 6 meaning | Phase 7 meaning                     |
| ------------------------------------------- | --------------- | ----------------------------------- |
| `attempts`                                  | always 1        | the number of model calls made      |
| `input_tokens`, `output_tokens`, `cost_usd` | the one call    | the sum over all attempts           |
| `prompt_version`                            | the one prompt  | the version of the **first** prompt |

`prompt_version` is the first prompt on purpose: it is the prompt that is
comparable with the Phase 5 and Phase 6 baselines, and it does not move when a
repair happens. The version of every later prompt is in the attempts file.

**D7 — The per-attempt record is a new file.** A new dated file
`<stamp>_attempts.toml` sits next to the agent file and holds one
`[[attempts]]` block per attempt, with the task and part identity, the attempt
number, its prompt version, tokens and cost, the status, the outcome, its
score, the failed check names and the error text. The eleven-field agent file
and the five-field result file are untouched. The attempts file is a record
for the operator: the agent path never reads it and it never enters a prompt.

**D8 — The stop conditions are deterministic and checked in this order.**

1. the candidate passes every required check — stop, the task is `ok`;
2. the attempt limit is reached — stop;
3. the cumulative cost or the cumulative token budget would be passed — stop
   before the call;
4. the build failed with a failure kind that is not in the candidate — stop;
5. the model call failed or the answer was empty — stop.

**D9 — Two failure kinds are not repairable.** `runner_crash` and
`input_error` describe a failure of the runner or of the request, not of the
part file, so a rewrite cannot fix them and the loop stops. The other six
kinds — `rejected_unsafe`, `syntax_error`, `runtime_error`, `timeout`,
`invalid_geometry` and `export_failed` — are all repairable by writing the
file again, and all of them produce feedback.

**D10 — The score of a task is the score of the last judged candidate.** The
Phase 4 scoring rule is untouched: [`score_task()`](../aturb/evals/scoring.py:25)
still computes `max_score * passed / required`, and the five-field
[`TaskResult`](../aturb/evals/result.py:30) still says what the geometry
scored. The loop only gives the agent another chance before the score is taken.

**D11 — The task set grows with two harder tasks.** Both are plates with
features a single shot can get wrong: a rectangular pocket of a given depth,
and a stepped plate with a fillet on the boss. Every expected value is
measured in real FreeCAD and read back with build123d, never guessed, and the
reference part follows the conventions and passes the unchanged precheck.

**D12 — The Phase 7 baseline records attempt 1 and the final attempt.** One
run with the attempt limit at its default gives both numbers, because the
attempts file holds the score of every attempt. The baseline is a recorded
measurement, like the Phase 5 and Phase 6 ones, and a model call is not
deterministic.

**D13 — The ADR index is brought up to date.** ADR-0008 and ADR-0009 are
listed in [`docs/adr/README.md`](adr/README.md).

## The failure-to-feedback contract

| The agent is told                                        | The agent is never told                                           |
| -------------------------------------------------------- | ----------------------------------------------------------------- |
| the build status and the failure kind                    | the expected value of any check                                   |
| the sanitized build error text and the traceback         | the tolerance of any check                                        |
| the informational diagnostics of the CAD                 | the name of any evaluator check                                   |
| the advisory convention findings                         | the verdict of any individual check                               |
| the candidate-only geometry summary of the exported STEP | the failure message of any evaluator check, the score of the task |
|                                                          | the answer file, the answer spec, `project/expect/`               |
|                                                          | the text or path of the expectation file                          |

**Why the candidate-only summary is safe.** Every number in it is a
measurement of the candidate the agent itself wrote, taken from the STEP the
candidate exported. It says what the agent built, not what the answer is. For
the fillet task the expected volume of 35175.973506 mm³ is not derivable from
the requirement, and no measurement of the candidate reveals it: the agent is
told that its own volume was wrong, not what the right volume is. There is no
residual hint either: no evaluator check name, verdict, tolerance or message
crosses the boundary, so the feedback says nothing about how many checks the
task has or what they are.

## The bounded loop

The loop for one task, in the order the steps happen:

1. prepare the scratch task ([`prepare_candidate_task()`](../aturb/agent/workspace.py:33));
2. compose the base prompt and call the model once;
3. write the candidate and judge it with the evaluator;
4. if the judgement is `ok`, stop;
5. if the attempt limit or the budget is reached, stop;
6. if the failure kind is not repairable, stop;
7. otherwise build the feedback, compose the repair prompt, call the model
   again, and go back to step 3.

The budget is checked **before** every call, with the same estimate the
single-shot path uses ([`estimate_input_tokens()`](../aturb/agent/run.py:142)).

## The record

| File                    | Holds                                         | Grows in Phase 7 |
| ----------------------- | --------------------------------------------- | ---------------- |
| `<stamp>_agent.toml`    | one `[[runs]]` block per task, eleven fields  | no               |
| `<stamp>_attempts.toml` | one `[[attempts]]` block per attempt          | new file         |
| `<stamp>.toml`          | one `[[results]]` block per task, five fields | no               |

The result file is the Phase 4 file and does not change, the agent file keeps
its eleven fields and its format, and the attempts file is the only new file.

## Evaluation strategy

- The task set grows by two tasks (D11). The existing two tasks stay exactly
  as they are, so the Phase 6 measurement stays comparable.
- The loop is measured on the whole set with the attempt limit at its default.
  The attempts file gives the score of attempt 1 and the score of the final
  attempt for every task, so the lift is a measured number. The comparison is
  between two recorded measurements, not two functions: a model call is not
  deterministic, and the baseline says so. The Phase 7 baseline is written
  next to the Phase 5 and Phase 6 baselines, in the same shape.

## Dependencies and task sequence

T7.01 → T7.02 → T7.03 → T7.04 → T7.05 → T7.06 → T7.07 → T7.08 → T7.11 → T7.12

T7.09 and T7.10 (the two harder tasks) wait for T7.02, because a task is only
worth adding when the feedback contract can describe its failure; T7.11 waits
for the loop, the settings and the two tasks, and T7.12 waits for T7.11.

## Acceptance criteria

The phase is accepted when:

- the loop is bounded by an explicit attempt limit and by cumulative token and
  cost caps, and it stops on the deterministic conditions of D8;
- the repair feedback carries no evaluator field — no expected value, no
  tolerance, no check name, no verdict, no evaluator message, no score and no
  expectation content — and a test proves it from the type, not from a
  convention;
- the first attempt sends the Phase 6 prompt unchanged;
- the agent-run record keeps its eleven fields, and the per-attempt detail is
  in the new attempts file;
- the task set holds two tasks that a single shot can get wrong, with every
  expected value measured in real FreeCAD;
- the Phase 7 baseline records attempt 1 and the final attempt for every task;
- `uv run pytest -m "not freecad" -q`, `uv run pytest -q`,
  `uv run ruff check .`, `uv run python tools/size_limit.py` and
  `uv run python tools/agnostic_lint.py` all pass, and the runner contract,
  the answer schema, the result record, the scoring rule and the precheck are
  unchanged.

## Scope boundaries and exclusions (locked for Phase 7)

Phase 7 does not introduce:

- a runner contract change or a contract version bump: the version stays `0.1`
  and the eight failure kinds stay eight;
- a change to [`packs/freecad/precheck.py`](../packs/freecad/precheck.py:7) or
  to its import allowlist;
- an answer-schema change, an evaluation-result schema change, a change to
  the eleven fields of the agent-run record or a change to the Phase 4 scoring
  rule;
- a change to the expectation files of the existing tasks or to the Phase 5 or
  Phase 6 baseline;
- a geometry DSL, an intermediate representation, a tool per CAD operation or a
  feature-creation helper, and any change to the boundary of ADR-0007;
- a ReAct loop, an autonomous tool-calling agent, a retry storm or a
  multi-agent system;
- GUI functionality, a new external dependency or a CAD-specific concept
  inside `aturb/`.

## Architectural risks

| risk                                       | what it would break                  | what keeps it small                                                                        |
| ------------------------------------------ | ------------------------------------ | ------------------------------------------------------------------------------------------ |
| R1 the feedback leaks the answer           | the evaluation proves nothing        | the feedback formatter takes candidate-side inputs only, and a test reads the type         |
| R2 the loop never stops                    | the run costs without bound          | the attempt limit, the cumulative caps and the ordered stop conditions                     |
| R3 the loop repairs by guessing            | the score rises for the wrong reason | the feedback carries candidate measurements, not targets, and the score rule is untouched  |
| R4 the record grows and breaks its readers | the Phase 5 and Phase 6 records      | the agent file keeps eleven fields; the detail goes to a new file                          |
| R5 the harder tasks are not harder         | the lift is zero and unmeasured      | the tasks are chosen for known weak spots, and the baseline records the outcome either way |
| R6 one model call is noisy                 | the lift is not a proof              | the baseline records the model, the prompt versions, the date and the per-attempt scores   |

## Relationship to Phase 8

Phase 8 and later are outside this assignment. The attempts file says what
failed at each attempt, so a later phase can study the unrepaired failures.

## Open questions

- Which two harder tasks to add is decided by the cards T7.09 and T7.10, not
  here; the requirement is that a single shot can fail on them and that the
  neutral checks can judge them unambiguously.
- The attempt limit and the cumulative caps are starting defaults. The Phase 7
  baseline may show that a different bound is better; the baseline records
  what was measured, and changing a bound is a later decision.
- The price of the tokens of the provider is still unverified
  ([`docs/api_notes/model.md`](../docs/api_notes/model.md:80)), so the recorded
  cost is the cost the configuration can compute, not a measured bill.
