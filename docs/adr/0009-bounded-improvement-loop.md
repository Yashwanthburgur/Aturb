# ADR-0009: The bounded improvement loop

Date: 2026-11-22
Status: Accepted

## Context

The agent path is one task, one model call, one candidate file, one build and
one score ([`docs/PHASE7_ROADMAP.md`](../PHASE7_ROADMAP.md:20)). The Phase 6
baseline scored 1.0 on both committed tasks with one attempt each, so the
current task set cannot show whether a repair loop helps: there is nothing to
repair.

A repair loop needs a feedback contract. The first draft of that contract
carried the names of the checks that did not pass, the measured actual value
and the tolerance of each failed check. Every one of those fields is
evaluator-side: the name, the verdict, the expected value, the tolerance and
the message all come from the expectation file
([`docs/adr/0008-exclude-expectations-from-prompt.md`](0008-exclude-expectations-from-prompt.md)).
Forwarding them would reopen the leak that ADR-0008 closed, and a failing
check name would also imply how many checks the task has.

The loop also needs a record of every attempt, and it must not change the
contracts the evaluation already depends on.

## Decision

**The loop is bounded and lives in the agent layer.** The loop is a new module
in [`aturb/agent/`](../../aturb/agent/), not in the evaluator and not in a pack.
It is bounded by an explicit attempt limit, by cumulative token caps and by a
cumulative cost cap, and the budget is checked before every call, with the
same estimate the single-shot path uses. The bounds are configuration values
with starting defaults; their numbers are not fixed here.

**The stop conditions are deterministic and checked in this order.**

1. the candidate passes every required check — stop, the task is `ok`;
2. the attempt limit is reached — stop;
3. the cumulative cost or the cumulative token budget would be passed — stop
   before the call;
4. the build failed with a failure kind that is not repairable — stop;
5. the model call failed or the answer was empty — stop.

**Two failure kinds are not repairable.** `runner_crash` and `input_error`
describe a failure of the runner or of the request, not of the part file, so a
rewrite cannot fix them and the loop stops. The other six kinds of
[`FailureKind`](../../aturb/contract/types.py:11) — `rejected_unsafe`,
`syntax_error`, `runtime_error`, `timeout`, `invalid_geometry` and
`export_failed` — are repairable by writing the file again, and all of them
produce feedback.

**There is no unbounded loop.** No unbounded retries, no ReAct framework, no
autonomous tool calling, no multi-agent logic and no background summarizer.

**Attempt 1 sends the Phase 6 prompt unchanged.** The repair prompt is the
five-section prompt of ADR-0008 plus one section, and the section is empty
when there is no feedback. The first attempt of a run therefore sends exactly
the Phase 6 prompt, and a run with an attempt limit of one reproduces the
single-shot path exactly.

**The repair feedback carries candidate-side inputs only.** It may carry:

- the build status and the failure kind;
- the sanitized build error text and the sanitized traceback;
- the informational diagnostics of the build, which
  [`docs/adr/0005-checks-on-step.md`](0005-checks-on-step.md) already calls
  hints and never a verdict;
- the advisory convention findings of the candidate file;
- an independent candidate-only geometry summary, measured from the exported
  STEP of the candidate when the build status is `ok`: whether the model is
  valid, whether it is a single solid, the measured volume, the size of its
  bounding box, and the detected holes with their count, their diameters and
  their positions.

**The repair feedback never carries an evaluator-derived field.** It must not
carry the expected value of a check, the tolerance of a check, the name of an
evaluator check, the verdict of an individual check, the failure message of an
evaluator check, the score of the task, the answer file, the answer spec, the
contents or the path of `project/expect/`, or a raw
[`CheckResult`](../../aturb/verify/result.py:20). The agent is told what its own
candidate measured, never which check failed and never what the target was.

**The leak is prevented by the type and the parameters, not by a convention.**
There is no safe view of a check, because every field of a check result is
evaluator-side. The type that crosses the boundary is the candidate-only
geometry summary, measured from the exported STEP of the candidate alone, and
the feedback formatter takes candidate-side inputs only: it has no parameter
that could carry an expectation path, an expectation dictionary or an answer
spec.

**The evaluator stays the judge and the only reader of the expectation file.**
The agent layer never reads `project/expect/`. The evaluator reads it and
judges the candidate; nothing it learns crosses into the agent layer. The
scratch workspace keeps `project/expect/`, as ADR-0008 requires.

**The agent-run record keeps its eleven fields.** The record of
[`aturb/agent/record.py`](../../aturb/agent/record.py:27) does not grow, so every
reader of it keeps working. Three fields change meaning, and only in the
direction of more information: `attempts` is the number of model calls made,
`input_tokens`, `output_tokens` and `cost_usd` are the sums over all attempts,
and `prompt_version` is the version of the first prompt, because that is the
prompt that is comparable with the earlier baselines.

**The per-attempt detail goes to a new dated file.** A new
`<stamp>_attempts.toml` sits next to the agent file and holds one
`[[attempts]]` block per attempt, with the task and part identity, the attempt
number, the prompt version of that attempt, the tokens and the cost of that
attempt, the status, the outcome, the score of that attempt, the names of the
checks that did not pass and the error text. It is a record for the operator:
the agent path never reads it and it never enters a prompt.

**The evaluation contracts are frozen.** The runner contract stays at version
`0.1` with its eight failure kinds, the static precheck of the pack is
unchanged, [`run_task()`](../../aturb/evals/runner.py:40) keeps its signature and
its five-field [`TaskResult`](../../aturb/evals/result.py:30), the answer schema
keeps its five keys, and the Phase 4 scoring rule is untouched. The score of a
task is the score of the last judged candidate; the loop only gives the agent
another chance before the score is taken.

This record states the decision. The code change that follows it is a separate
card.

## Consequences

The agent can be told what its own candidate measures without being told
anything the evaluator knows, so the repair loop cannot leak the answer and
the evaluation still proves something.

The first attempt of a run is byte-identical to the Phase 6 prompt, so the
Phase 6 baseline stays comparable and the lift of attempt 1 against the final
attempt is a measured number.

The loop cannot run without bound: the attempt limit, the cumulative caps and
the ordered stop conditions end every run, and the two unrepairable failure
kinds stop it before a rewrite that cannot help.

The eleven fields of the agent-run record and the five fields of the result
record do not change, so every reader of them keeps working, and the detail
of each attempt lives in one new file.

The Phase 4 evaluation contracts, the scoring rule and the expectation files
are unchanged: the evaluator still reads the same files and still scores the
same way.
