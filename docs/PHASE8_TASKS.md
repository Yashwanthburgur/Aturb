# Phase 8 task cards — expectation-free arbitrary-prompt generation

These cards implement [`docs/PHASE8_ROADMAP.md`](PHASE8_ROADMAP.md) and
[`docs/adr/0010-arbitrary-prompt-generation.md`](adr/0010-arbitrary-prompt-generation.md).
Every card is small, file-scoped and gate-checked. The runner contract, static
precheck, answer schema, evaluation result, agent-run record and scoring rule
remain frozen.

Rules every card inherits:

- The core stays CAD-neutral and no new external dependency is added.
- Generation never creates task, answer or expectation files and never reports
  a correctness score.
- Repair feedback carries candidate-side inputs only.
- Every build clears the current part's previous output directory first.
- The loop has explicit attempt and cumulative budget bounds and no hidden retry.
- Files stay at or below 300 lines; chosen defaults are marked as starting
  defaults; no card stages, commits or pushes.

## T8.01 — Roadmap, task cards and ADR-0010

GOAL: Record the expectation-free architecture and the bounded work sequence.

FILES (only these): `docs/PHASE8_ROADMAP.md`, `docs/PHASE8_TASKS.md`,
`docs/adr/0010-arbitrary-prompt-generation.md`, `docs/adr/README.md`

DO EXACTLY:

1. Place arbitrary-prompt generation beside, not inside, the fixed-task
   evaluator and identify the existing agent, runner, STEP and feedback seams.
2. Decide that no task, answer or expectation is fabricated and that no judge,
   scoring function or correctness score is used.
3. Specify per-attempt output deletion and the four build/STEP feedback mappings,
   including readable invalid or multi-solid geometry with `Build: ok`.
4. Specify the editable source, STEP, optional native artifact and relative-path
   `result.toml` output contract.
5. Define T8.01 through T8.05, deferring the live-model run to T8.05, and index
   ADR-0010 in the existing format.

DO NOT: name a backend or backend API in ADR-0010; change implementation; add a
failure kind, schema, operations layer, framework, GUI or dependency.

ACCEPTANCE: file-size, agnosticism and lint gates pass; the ADR is at most 180
lines and each roadmap document is at most 240 lines.

EVIDENCE: the four documents and their diff.

DEPENDS ON: Phase 7.5 reliability hardening.

## T8.02 — Expectation-free bounded generation service

GOAL: Build and repair one arbitrary-prompt candidate in an isolated standalone
workspace.

FILES (only these): `aturb/agent/generate.py`, `tests/test_agent_generate.py`

DO EXACTLY:

1. Add a frozen generation result carrying status, identity, workspace and
   artifact paths, build outcome, geometry, conventions, attempts, usage, first
   prompt version, stop reason and error.
2. Validate non-empty requirements, safe single-segment part identities and
   numeric loop bounds. Return an error result rather than raising.
3. Read the pack prompt, create only `project/parts/` and `project/out/`, and
   reuse `PreparedTask` and `run_attempt()` for each candidate.
4. Check cumulative input, output and cost caps before every model call and sum
   actual usage over completed calls.
5. Delete and recreate `project/out/<part_id>` immediately before every build.
6. Map failed builds, missing STEP, unreadable STEP and readable invalid or
   multi-solid STEP exactly as ADR-0010 states. Finish immediately on a valid
   single solid.
7. Stop at the attempt limit, on `runner_crash` or `input_error`, on budget
   refusal and on model error. Otherwise render candidate-only repair feedback
   with the previous source and continue.
8. Test success, syntax repair, usage totals, stable first prompt version, stale
   artifact removal, invalid or multi-solid repair feedback, every stop
   condition and invalid input. Use fake clients and runners only.

DO NOT: import evaluation task, answer or scoring modules; read expectations;
create evaluation fixtures; add a failure kind; modify the frozen feedback or
attempt modules; use a network or live model.

ACCEPTANCE: the new tests, lint, file-size and agnosticism gates pass; the
implementation and test files are each at most 290 lines.

EVIDENCE: targeted test output, static gates and the two-file diff.

DEPENDS ON: T8.01.

## T8.03 — Command handler, engineering report and viewer manifest

GOAL: Expose generation through a thin handler and leave a portable result for
people and downstream tools.

FILES (only these): `aturb/agent/generate_cli.py`, `tests/test_generate_cli.py`

DO EXACTLY:

1. Add a `generate` parser with an optional positional prompt, `--prompt-file`,
   `--out`, `--part-id`, `--max-attempts`, `--config` and `--pack`.
2. Refuse missing or competing prompt sources with exit 2. Default the output
   to a dated directory and allow the attempt flag to override configuration.
3. Load the selected pack and runner, resolve agent settings and construct the
   client through an injected factory. Convert configuration and credential
   errors to clean exit-2 messages.
4. Call the generation service, write `<workspace>/result.toml`, print a
   scannable engineering report and return 0 only for a built result.
5. Write hand-written TOML with the existing string escaper. Use relative
   source, STEP and native paths and include status, stop reason, attempts,
   usage, build outcome, conventions and measured geometry when available.
6. Test TOML parsing, relative paths, failed results, geometry and hole
   rendering, advisory findings, sanitized errors, both prompt sources, output
   and attempt overrides, and exit codes 0, 1 and 2.

DO NOT: add a TOML dependency, absolute manifest path, score, expectation,
traceback for expected input errors, backend concept or GUI.

ACCEPTANCE: the new tests, lint, file-size and agnosticism gates pass; each new
file is at most 270 lines.

EVIDENCE: targeted test output, static gates, a sample manifest and report.

DEPENDS ON: T8.02.

## T8.04 — Command registration and end-to-end proof

GOAL: Make `aturb generate` available without changing any existing command.

FILES (only these): `aturb/cli.py`, `tests/test_generate_end_to_end.py`

DO EXACTLY:

1. Register the generation parser and dispatch its handler while preserving all
   existing flags, printed lines and exit codes. Keep the CLI at most 300 lines.
2. With a monkeypatched client factory and the stub pack, prove one-attempt
   success, two-attempt syntax repair, prompt-file input and missing-prompt
   exit 2. Assert source, STEP and manifest outputs and the absence of every
   evaluation fixture.
3. With the real backend and a canned two-answer client, prove syntax repair,
   a valid single-solid plate with one centred through-hole, measured geometry,
   a parseable relative-path manifest and an untouched committed task set.
4. Mark the real-backend test only with the existing backend marker. Make no
   network or live-model call and remove temporary artifacts from committed
   folders.

DO NOT: modify the existing CLI tests, runner, pack, evaluator, task set or
configuration schema; add another marker; invoke a live model.

ACCEPTANCE: targeted generation and existing CLI tests pass, the offline and
full suites pass, `aturb generate --help` works, and all static gates pass.

EVIDENCE: complete test and gate output, measured real-backend geometry, sample
manifest and report, and the exact Git status.

DEPENDS ON: T8.03.

## T8.05 — Interactive live-model verification run

GOAL: Record one real arbitrary-prompt generation through the interactive CLI
after the implementation cards have been reviewed.

FILES (only these): `docs/PHASE8_BASELINE.md`; git-ignored generation output

DO EXACTLY:

1. Choose a self-contained requirement with no evaluation answer or expected
   fixture and run `aturb generate` once with the configured provider and active
   real backend.
2. Record the date, provider and model identifiers, prompt versions, attempt
   count, stop reason, token totals, configured cost calculation, output paths
   and measured candidate geometry.
3. Preserve the exact command and console report. Inspect the editable source,
   STEP, optional native artifact and `result.toml` without changing the run to
   improve its appearance.
4. Record failures exactly, including reasoning exhaustion, budget refusal,
   build failure or invalid geometry. State that one run is not deterministic
   and is not a general correctness claim.

DO NOT: run this card with the offline implementation cards; fabricate a task,
answer, expectation or score; expose a credential or raw private response;
modify the committed task set; claim broader autonomy from one example.

ACCEPTANCE: the baseline contains the exact command, console output, manifest,
measured geometry and an explicit account of every attempt and stop condition.

EVIDENCE: the baseline and git-ignored output workspace.

DEPENDS ON: reviewed and accepted T8.04.
