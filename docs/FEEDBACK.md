# The repair feedback contract

What the repair prompt of a bounded improvement loop may carry, and what it must
never carry. This document is the contract of the card T7.02 of
[`docs/PHASE7_TASKS.md`](PHASE7_TASKS.md). The decisions behind it are D2 to D5
of [`docs/PHASE7_ROADMAP.md`](PHASE7_ROADMAP.md) and
[`docs/adr/0009-bounded-improvement-loop.md`](adr/0009-bounded-improvement-loop.md).
The information boundary of the prompt itself is
[`docs/adr/0008-exclude-expectations-from-prompt.md`](adr/0008-exclude-expectations-from-prompt.md).

This document is CAD-neutral: it names no CAD, no CAD API and no backend, it
does not restate the runner contract, and it holds no expected value of any
task.

The card T7.5.1 of Phase 7.5 added the source code of the previous candidate
to the list of permitted inputs. Every other rule of this contract is
unchanged.

## The two lists

### What the repair prompt may carry

The repair prompt may carry candidate-side inputs only. Every item below is
produced by, or measured from, the candidate the agent itself wrote.

1. **The build status and the failure kind.** The status says whether the
   candidate built; the failure kind says how it failed, when it failed.
2. **The sanitized build error text and the sanitized traceback.** Sanitizing
   removes absolute paths, drive letters and machine-specific values, so the
   text can be shown without carrying the machine the build ran on.
3. **The informational build diagnostics.** These are hints, never a verdict:
   they are reported to the agent and are never used to pass or fail anything
   ([`docs/adr/0005-checks-on-step.md`](adr/0005-checks-on-step.md)).
4. **The advisory convention findings** of the candidate file, from
   [`check_conventions()`](../aturb/agent/conventions.py:65). A finding is
   reported and nothing more: it never blocks a build, never becomes a failure
   of its own and never changes the score of a task.
5. **The candidate-only geometry summary**, measured from the exported STEP of
   the candidate when the build status is `ok`. It is specified below.
6. **The source code of the previous candidate.** The file the agent itself
   wrote on the previous attempt, exactly as it was written. It is the
   candidate's own text, so the next attempt can read its own code, find the
   concrete mistake in it and fix it. It is never the reference part, never a
   file of the evaluator and never an expectation file.

### What the repair prompt must never carry

The repair prompt must never carry a field that the evaluator derived. The
forbidden list is:

- the expected value of any check;
- the tolerance of any check;
- the name of any evaluator check;
- the verdict of any individual check, passed or failed;
- the failure message of any evaluator check;
- the score of the task;
- the answer file and the answer spec;
- the contents, the text, the path and the file name of `project/expect/`;
- any raw check result, and any check view of any kind.

The agent is told what its own candidate measured. It is never told which check
failed, and never told what the target was.

## The candidate-only geometry summary

The summary is measured from the exported STEP of the candidate alone, with the
neutral readers of the core
([`load_step()`](../aturb/verify/step.py:90) and
[`find_holes()`](../aturb/verify/holes.py:48)). It is never measured from, or
compared with, the expectation file.

| Field             | What it says                                                                 | Unit          |
| ----------------- | ---------------------------------------------------------------------------- | ------------- |
| `is_valid`        | the model holds solids and every one of them is valid                        | boolean       |
| `is_single_solid` | the file holds exactly one solid                                             | boolean       |
| `volume`          | the total volume of the solids of the model                                  | mm³           |
| `bbox_size`       | the size of the bounding box of the whole model, as X, Y and Z               | mm            |
| `holes`           | the detected holes: their count, their diameters and their X and Y positions | count, mm, mm |

**The summary is present only when the build status is `ok` and a STEP file was
exported.** A build that failed has no geometry to measure, so the section is
left out.

**The summary carries no comparison.** It holds no expected value, no
tolerance, no check name and no verdict, so it cannot say whether the candidate
is right. The summary reports what the candidate itself measures. It contains no
comparison with a target and gives no indication of whether any evaluator check
passed or failed.

**The summary is independent of the evaluation.** It is measured from the
candidate's own exported file, so it is the same whether the candidate passed
or failed, and it reveals nothing about the number of checks the task has.

## The structural boundary

**The formatter takes candidate-side inputs only.** The feedback formatter is
called with five inputs and nothing else:

- `build` — the build outcome: the status, the failure kind, the sanitized
  error text and the sanitized traceback;
- `diagnostics` — the informational build diagnostics;
- `conventions` — the advisory convention findings;
- `geometry` — the candidate-only geometry summary;
- `previous_code` — the source code of the candidate the agent wrote on the
  previous attempt.

**The previous candidate is the agent's own text.** It is the file the agent
wrote, so it is candidate-side by definition: it is never the reference part,
never the expectation file and never any other file of the evaluator. Carrying
it opens no path to an evaluator value, so
[`docs/adr/0008-exclude-expectations-from-prompt.md`](adr/0008-exclude-expectations-from-prompt.md)
still holds: the agent path still never reads `project/expect/`, and the
evaluator stays the judge.

**There is no evaluator input to pass.** The formatter has no parameter for an
expectation path, no parameter for an expectation dictionary and no parameter
for an answer spec, so an evaluator value cannot reach the rendered text even
by accident. No raw check result and no check view of any kind crosses into
the agent layer. The leak is therefore prevented by the type and the
parameters, not by a convention: a formatter that could be handed an evaluator
field does not exist, because there is no parameter that could receive one.

**The agent path never reads `project/expect/`.** The evaluator stays the judge
and the only reader of the expectation file. The scratch workspace keeps
`project/expect/`, as ADR-0008 requires, and the agent path still never opens
it.

## The shape of the repair feedback block

The block is rendered in this order, and a section that has nothing to say is
left out:

1. the fixed repair instruction — the previous file is replaced by the file
   written now, and the answer is still only the file;
2. the build outcome — the status and, when the build failed, the failure kind;
3. the sanitized error text and the sanitized traceback, when the build failed;
4. the informational build diagnostics, when the build reported any;
5. the advisory convention findings, when the checker found any;
6. the candidate-only geometry summary, when the build status is `ok` and a
   STEP file was exported;
7. the source code of the previous candidate, when the agent wrote one.

The source code is fenced, so its indentation is preserved verbatim and the
agent reads its own file exactly as it wrote it. The fence is a run of
backticks long enough that no line of the code can close it.

The block is empty when the candidate passed every check: there is nothing to
repair, so the next attempt sends the prompt of the first one. The first
attempt carries no block, so its prompt is the single-shot prompt.

## Worked example 1 — a build that failed

The candidate did not build, so there is no geometry to measure and the
geometry section is left out.

```
## Repair

The previous file is replaced by the file you write now. The answer is still
only the file.

Build: failed (syntax_error)

Error:
  File "plt9001_base.py", line 12
    width = 40
SyntaxError: invalid syntax

Traceback (most recent call last):
  File "plt9001_base.py", line 12, in <module>
    width = 40
SyntaxError: invalid syntax
```

The block says how the build failed and nothing about the evaluation: no check
is named and no expected value or tolerance is carried.

## Worked example 2 — a candidate that built and exported STEP

The candidate built, so the block carries the candidate-only geometry summary.
The build reported no diagnostics, so that section is left out.

```
## Repair

The previous file is replaced by the file you write now. The answer is still
only the file.

Build: ok

Convention findings:
  C2: the parameter block is missing, so the dimensions are not named constants

Candidate geometry (measured from the exported STEP):
  is_valid: true
  is_single_solid: true
  volume: 41237.5 mm^3
  bbox_size: 97.0 x 43.0 x 8.0 mm
  holes: 3
    hole 1: diameter 6.0 mm, position (-21.5, 0.0) mm
    hole 2: diameter 6.0 mm, position (0.0, 12.5) mm
    hole 3: diameter 4.5 mm, position (21.5, 0.0) mm
```

The numbers in this example are synthetic. They are not the expected values of
any task, and they are not a target: the summary says what this candidate
measures, not what it should measure. The convention finding is advisory.

## Worked example 3 — a candidate that is carried back

The candidate of the previous attempt is carried back verbatim, so the next
attempt can read its own code and fix the mistake in it.

````
## Repair

The previous file is replaced by the file you write now. The answer is still
only the file.

Build: failed (syntax_error)

Error:
  File "plt9001_base.py", line 12
    width = 40
SyntaxError: invalid syntax

Previous candidate:

```
# the candidate of the previous attempt
def build(doc):
    return doc
```
````

The code is the candidate's own text and nothing else. It names no check, no
expected value and no tolerance, and it is not the reference part.

## Boundaries

**This document names no CAD and does not restate the runner contract.** The
feedback is CAD-neutral: the same contract holds for every backend, and the
geometry summary is read from the exported file with the neutral readers of the
core. The build status and the failure kind are inputs of the feedback, not a
description of the contract that produced them.

**This document holds no expected value.** No expected value of any committed
or planned task appears here, and none may be added: the document describes the
shape of the feedback, not the answer of a task.

**The evaluator stays the judge.** The candidate is judged against the
expectation file by the neutral checks, independently of what the agent was
told. The repair loop gives the agent another chance; it does not change how a
task is scored.
