# ADR-0010: Expectation-free arbitrary-prompt generation

Date: 2026-11-24
Status: Accepted

## Context

The evaluation path starts from a task folder. It reads a task identity, an
answer specification and evaluator expectations, then builds and scores a
candidate. That path proves performance on a fixed task set, but it cannot serve
a user who has only an engineering requirement and wants an editable part.

The new command must reuse the code-first agent, the runner boundary, neutral
STEP measurement and the bounded repair feedback of ADR-0001, ADR-0004,
ADR-0005 and ADR-0009. It must not manufacture an evaluation task in order to
reuse the evaluator, and it must not turn candidate-side measurements into a
correctness claim.

A shared output workspace introduces another hazard. A failed or incomplete
later attempt must never inherit an artifact left by an earlier attempt.

## Decision

**Generation is expectation-free.** `aturb generate` accepts an arbitrary
engineering requirement and creates a standalone workspace containing only the
folders needed for candidate source and build outputs. It never fabricates
`task.toml`, `answer.toml` or `project/expect/`, never invokes `judge_task()` or
`score_task()`, and never reports a correctness score. A successful result says
that the candidate built and exported one readable, valid single solid; it does
not say that the part satisfies an unstated target.

**The agent still writes source code.** There is no geometry language,
intermediate representation, operation tool layer, autonomous tool-calling
framework or multi-agent system. The active pack supplies the source language,
file extension, prompt and runner. The core remains independent of every backend.

**The loop is bounded and candidate-side.** The existing attempt primitive and
prompt composer are reused. An explicit attempt limit and cumulative input,
output and cost caps are checked before every model call. Repair feedback uses
only the previous candidate, its sanitized build outcome, informational
diagnostics, advisory convention findings and geometry measured from its own
exported STEP. No evaluator object or expectation enters the loop.

**Every attempt has isolated artifacts.** Before every build attempt in a shared
output workspace, `project/out/<part_id>` is removed and recreated. A stale STEP
or native artifact from attempt N-1 therefore cannot be mistaken for the output
of attempt N. A runner-reported path is accepted only when the named file exists
in the freshly cleared workspace.

**Invalid geometry uses the existing contract.** No failure kind is added.
Build and STEP outcomes become repair feedback as follows:

1. When `build.status != "ok"`, feedback carries the existing
   `build.failure_kind` and sanitized `error_text`, and geometry is absent.
2. When the build reports success but supplies no readable STEP artifact, the
   feedback is `BuildFeedback(status="failed", failure_kind="export_failed",
error_text="the build produced no STEP file")`, and geometry is absent.
3. When STEP reading raises `StepLoadError`, the feedback is
   `BuildFeedback(status="failed", failure_kind="invalid_geometry",
error_text=sanitize_text(...))`, and geometry is absent.
4. When STEP loads but is invalid or is not a single solid, the feedback is
   `BuildFeedback(status="ok", failure_kind="",
error_text="exported STEP is invalid or not a single solid")`. The measured
   candidate geometry is retained, so the existing formatter renders `Build:
ok`, the candidate-only error note, validity and solidity measurements,
   advisory conventions and the previous source. The eight existing failure
   kinds and the feedback module remain unchanged.

The two infrastructure failure kinds already declared unrepairable by ADR-0009
stop the loop. Other build failures may be repaired by replacing the candidate.
Reaching the attempt limit, refusing a cumulative budget before a call, or a
model-call failure also stops the loop deterministically.

**The output is useful outside the evaluator.** A completed workspace contains
the editable candidate source, the exported STEP when produced, the native
artifact when the pack produces one, and a CAD-neutral `result.toml` manifest.
The manifest sits at the workspace root and uses relative paths only. It records
the run status, stop reason, attempts, token and cost totals, prompt version,
build outcome, advisory findings and measured candidate geometry. It contains no
answer, expectation, score or machine-specific absolute path.

**The evaluation contracts stay frozen.** Runner contract `0.1`, its eight
failure kinds, the five-field task result, the five-key answer specification,
the eleven-field agent run, the dated evaluation records and Phase 4 scoring are
not changed. Arbitrary-prompt generation is a separate agent service and a thin
CLI client, not another evaluator mode.

## Consequences

A user can request a part without creating evaluation fixtures, and downstream
tools can locate the resulting source and artifacts through one portable
manifest. The command can report measured facts without pretending to know an
engineering target that was never supplied.

Artifact deletion makes each attempt's evidence causal: success can be attributed
only to files produced by that attempt. Invalid but readable geometry remains
visible to the model as candidate-side feedback without inventing a ninth
failure kind or changing the frozen formatter.

The command does not replace evaluation. Fixed tasks, independent expectations
and scoring remain the way to measure agent performance. A later live-model run
is a recorded verification of this path, not a general claim of engineering
correctness.
