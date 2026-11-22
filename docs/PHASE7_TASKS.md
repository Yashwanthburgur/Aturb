# Phase 7 task cards — the bounded improvement loop

Proposed cards for Phase 7, derived from
[`docs/PHASE7_ROADMAP.md`](PHASE7_ROADMAP.md). The roadmap holds the scope, the
decisions and the strategy; this file holds the work. Every card is small, has
one file scope, and can be tested on its own. The runner contract, the precheck,
the answer schema, the result record, the scoring rule and the eleven fields
of the agent-run record do not change in this phase.

Rules every card inherits:

- The core stays CAD-neutral; the runner contract does not change.
- The agent path never reads `project/expect/`, and the repair feedback carries candidate-side inputs only: no expected value, no tolerance, no check name, no verdict, no evaluator message, no score and no expectation content.
- The loop is bounded: an explicit attempt limit, cumulative token and cost caps, deterministic stop conditions.
- Only calls recorded in the API notes or verified in-session may be used; files at most 300 lines; every chosen default is marked `# starting default`; one card, one commit.

## T7.01 — The improvement-loop ADR and the ADR index

GOAL: One decision record that states the bounded loop, the feedback contract and the record.

FILES (only these): `docs/adr/0009-bounded-improvement-loop.md`, `docs/adr/README.md`

DO EXACTLY:

1. Write the ADR in the style of the existing records: title, date, status, context, decision, consequences.
2. Decide the bounded loop: an explicit attempt limit, cumulative token and cost caps, the ordered stop conditions, and the two failure kinds that are not repairable.
3. Decide the feedback contract: what the repair prompt may carry and what it must never carry, and that no evaluator field — no expected value, no tolerance, no check name, no verdict and no evaluator message — crosses into the agent layer.
4. Decide the record: the agent-run record keeps its eleven fields, `attempts` is the number of model calls, the tokens and the cost are cumulative, `prompt_version` is the version of the first prompt, and the per-attempt detail goes to a new dated file.
5. Add ADR-0008 and ADR-0009 to the index in `docs/adr/README.md`.

DO NOT: change an implementation file. Do not change the runner contract, the precheck, the answer schema, the result record or the scoring rule. Do not name a limit the roadmap does not fix.

ACCEPTANCE: `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK; `git diff --check` -> no output; `git status --short` lists only the two files; the index names ADR-0008 and ADR-0009.

EVIDENCE: the ADR file, the two index lines, the diff of the two files.

COMMIT: `docs(adr): define the bounded improvement loop`

DEPENDS ON: none.

## T7.02 — The repair feedback contract

GOAL: One document that states what the repair prompt may carry and what it must never carry.

FILES (only these): `docs/FEEDBACK.md`

DO EXACTLY:

1. State the contract as two lists: what the repair prompt may carry, and what it must never carry, and state the shape of the repair feedback block with one worked example of a failed build and one of a candidate that built and exported STEP.
2. State the candidate-only geometry summary: `is_valid`, `is_single_solid`, the measured volume, the bounding-box size and the detected holes with their count, diameters and positions, all measured from the exported STEP of the candidate alone.
3. State the forbidden evaluator fields: the expected value, the tolerance, the check name, the individual `passed` verdict and the failure message of any check, the score of the task, the answer file, the answer spec and the contents of `project/expect/`.
4. State that the feedback formatter receives candidate-side inputs only — the build outcome, the sanitized error text and traceback, the informational diagnostics, the convention findings and the candidate-only geometry summary — that it has no parameter for an expectation path, an expectation dictionary or an answer spec, and that no raw `CheckResult` and no check view crosses into the agent layer.

DO NOT: name a CAD. Do not restate the runner contract. Do not put the expected value of any task in the document. Do not describe a check view that carries evaluator fields.

ACCEPTANCE: `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK; `git diff --check` -> no output; the document holds both lists, the candidate-only geometry summary, the forbidden evaluator-field list and both worked examples.

EVIDENCE: the document, the diff.

COMMIT: `docs: state the repair feedback contract`

DEPENDS ON: T7.01.

## T7.03 — The judgement, and the task runner that judges once

GOAL: The evaluator judges a task once and hands the agent only what the candidate itself measures.

FILES (only these): `aturb/evals/judge.py`, `aturb/evals/runner.py`, `tests/test_evals_judge.py`, `tests/test_evals_runner.py`

DO EXACTLY:

1. Add a candidate-only geometry summary type with the fields `is_valid`, `is_single_solid`, `volume`, `bbox_size` and the detected holes with their count, diameters and positions, measured from the exported STEP of the candidate alone.
2. Add `judge_task(task_dir, runner, timeout_s)` that does what `run_task()` does today and returns a judgement holding the five-field result, the candidate-only geometry summary, the build status, the failure kind, the sanitized error text and the informational diagnostics; the score still comes from `score_task()`.
3. Keep `run_task(task_dir, runner, timeout_s) -> TaskResult` with its exact signature, its five-field `TaskResult` and the Phase 4 scoring rule completely frozen, and make it return the result of that one judgement.
4. Measure the candidate-only summary from the exported STEP of the candidate with the neutral readers of the core, never from the expectation file, and keep the existing tests of `tests/test_evals_runner.py` unchanged and passing, with one new test that the result of `run_task()` equals the result of `judge_task()` for the same task.

DO NOT: change the five fields of `TaskResult`, the five keys of `AnswerSpec`, the scoring rule or the contract. Do not add a check view, a `CheckResult` field or any evaluator field to the summary. Do not pass a `CheckResult`, an expectation dictionary, an expectation path or an `AnswerSpec` into `aturb/agent/`. Do not change the behaviour or the error text of any outcome.

ACCEPTANCE: `uv run pytest tests/test_evals_judge.py tests/test_evals_runner.py -q` -> all pass; `uv run pytest -m "not freecad" -q` -> all pass; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

EVIDENCE: the output of both test commands, the diff of the four files.

COMMIT: `feat(evals): judge a task once, without expected values`

DEPENDS ON: T7.02.

## T7.04 — The feedback and the repair prompt

GOAL: The candidate-side inputs become a text block, and the prompt of a repair carries it.

FILES (only these): `aturb/agent/feedback.py`, `aturb/agent/prompt.py`, `tests/test_agent_feedback.py`, `tests/test_agent_prompt.py`

DO EXACTLY:

1. Add `feedback_text(build, diagnostics, conventions, geometry) -> str` that renders the block of the contract of T7.02: the build outcome first, then the sanitized error text and traceback, then the informational diagnostics, then the advisory convention findings, then the candidate-only geometry summary.
2. Return an empty string when the candidate passed every check.
3. Add an optional `feedback` argument to `compose_prompt()` and insert the feedback section between the requirement and the output contract, so the prompt has six sections when there is feedback and five when there is not.
4. Give the section a fixed instruction: the previous file is replaced by the file written now, and the answer is still only the file.
5. Keep `prompt_version()` unchanged, keep the prompt of the first attempt byte-identical to the prompt of Phase 6, and give the formatter candidate-side inputs only: the build outcome, the sanitized error text and traceback, the informational diagnostics, the convention findings and the candidate-only geometry summary, with no parameter for an expectation path, an expectation dictionary or an answer spec.

DO NOT: read the expectation file. Do not print an expected value, a tolerance, a check name, an individual verdict, an evaluator failure message, the score, the checks that passed or the path of the expectation file. Do not accept or forward a `CheckResult`. Do not change the core instruction, the pack prompt, the conventions, the output contract or the order of the five sections.

ACCEPTANCE: `uv run pytest tests/test_agent_feedback.py tests/test_agent_prompt.py -q` -> all pass; the tests prove that no expected value, tolerance, check name, verdict, evaluator failure message, score or expectation content of the task appears in the rendered text, that `compose_prompt(pack, requirement)` gives the prompt of Phase 6, and that the formatter cannot be called with an evaluator field; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

EVIDENCE: the output of the test command, the diff of the four files.

COMMIT: `feat(agent): render repair feedback and carry it in the prompt`

DEPENDS ON: T7.03.

## T7.05 — One attempt, one run

GOAL: The single attempt becomes a piece the loop can call again.

FILES (only these): `aturb/agent/run.py`, `tests/test_agent_run.py`

DO EXACTLY:

1. Split `run_agent()` into the preparation of the scratch, an attempt that composes the prompt with the feedback, checks the limits, calls the model once and writes the candidate, and the record that is built from the attempt.
2. Keep `run_agent()` with its exact signature and its exact behaviour: one call, one candidate, `attempts = 1`, the same error texts.
3. Return the prompt version, the tokens and the cost of the attempt from the attempt, so a caller can add them up.
4. Keep the per-call limits exactly as they are: the input token cap and the cost budget are still checked before the call.

DO NOT: change the public behaviour of `run_agent()`. Do not add a retry. Do not change the error texts. Do not change the types of `aturb/agent/types.py`.

ACCEPTANCE: `uv run pytest tests/test_agent_run.py -q` -> all pass; the existing tests are unchanged and still pass; `uv run pytest -m "not freecad" -q` -> all pass.

EVIDENCE: the output of both test commands, the diff of the two files.

COMMIT: `refactor(agent): split one attempt from one run`

DEPENDS ON: T7.04.

## T7.06 — The bounded loop

GOAL: The agent gets another chance, a bounded number of times.

FILES (only these): `aturb/agent/loop.py`, `tests/test_agent_loop.py`

DO EXACTLY:

1. Add `run_agent_loop()` that prepares the scratch once, then repeats: attempt, judge, and either stop or build the feedback and try again.
2. Stop, in this order, when the candidate passes, when the attempt limit is reached, when the cumulative cost or the cumulative token budget would be passed, when the failure kind is `runner_crash` or `input_error`, and when the model call fails or the answer is empty.
3. Check the cumulative budget before every call, with the same estimate the single-shot path uses.
4. Return the agent run with `attempts` = the number of model calls, the tokens and the cost summed over the attempts, and `prompt_version` = the version of the first prompt.
5. Keep the file under 300 lines and the core CAD-neutral.

DO NOT: read the expectation file. Do not change the score rule or the result type. Do not add a retry storm, a ReAct loop or a tool call. Do not change the runner contract.

ACCEPTANCE: `uv run pytest tests/test_agent_loop.py -q` -> all pass; the test proves the loop stops at the attempt limit, at the budget and on an unrepairable failure kind; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

EVIDENCE: the output of the test command, the new file.

COMMIT: `feat(agent): add the bounded repair loop`

DEPENDS ON: T7.05.

## T7.07 — The record of every attempt

GOAL: Every attempt of a run is written down, and the agent file does not change.

FILES (only these): `aturb/agent/attempts.py`, `aturb/agent/record.py`, `tests/test_agent_record.py`

DO EXACTLY:

1. Add the `AttemptRecord` type with the task and part identity, the attempt number, the prompt version, the tokens, the cost, the status, the outcome, the score, the names of the checks that did not pass and the error text.
2. Write the attempts to a new dated file `<stamp>_attempts.toml` next to the agent file, with one `[[attempts]]` block per attempt, and read them back.
3. Leave the eleven fields of the agent file and the format of `<stamp>_agent.toml` exactly as they are.
4. Keep the hand-written TOML escaping of the existing writer and extend it to the new fields.

DO NOT: change the eleven fields of `AgentRun` or the keys of the agent file. Do not change the five fields of the result file. Do not add a dependency.

ACCEPTANCE: `uv run pytest tests/test_agent_record.py -q` -> all pass; the existing tests of the agent file are unchanged and still pass; `uv run python tools/size_limit.py` -> size_limit: OK.

EVIDENCE: the output of the test command, the diff of the three files.

COMMIT: `feat(agent): record every attempt of a run`

DEPENDS ON: T7.06.

## T7.08 — The settings and the command line

GOAL: The loop is configured, and the agent evaluation uses it.

FILES (only these): `aturb/agent/config.py`, `aturb/cli.py`, `tests/test_agent_config.py`, `tests/test_cli.py`

DO EXACTLY:

1. Add the settings `max_attempts` (default 3), `max_total_cost_usd`, `max_total_input_tokens` and `max_total_output_tokens`, each marked `# starting default`.
2. Keep `max_input_tokens`, `max_output_tokens` and `max_cost_usd` as the per-call caps, unchanged.
3. Make `aturb eval --agent` use the loop and write the attempts file next to the agent file; the printed lines, the summary and the exit codes stay exactly as they are.
4. Make `max_attempts = 1` reproduce the single-shot path exactly, with one call and one candidate.

DO NOT: change the exit codes, the printed lines or the result file. Do not change the per-call caps. Do not add a command-line flag.

ACCEPTANCE: `uv run pytest tests/test_cli.py tests/test_agent_config.py -q` -> all pass; `uv run pytest -m "not freecad" -q` -> all pass; `git diff --check` -> no output.

EVIDENCE: the output of both test commands, the diff of the four files.

COMMIT: `feat(agent): wire the loop into the agent evaluation`

DEPENDS ON: T7.07.

## T7.09 — A task with a pocket

GOAL: A task a single shot can get wrong, with every expected value measured.

FILES (only these): `evals/tasks/plate_pocket/task.toml`, `evals/tasks/plate_pocket/answer.toml`, `evals/tasks/plate_pocket/project/expect/plt0003.toml`, `evals/tasks/plate_pocket/project/requirements/plt0003.md`, `evals/tasks/plate_pocket/project/parts/plt0003_base_plate_pocket.py`, `evals/tasks/plate_pocket/project/parts/plt0003_base_plate_pocket.stub`

DO EXACTLY:

1. Add the task `plate_pocket` for the part `plt0003`: a 120 × 60 × 10 plate with a 40 × 20 rectangular pocket 4 mm deep, centred, and two 10 mm through-holes at x = −40 and x = +40 on y = 0.
2. Write the reference part so that `check_conventions("plt0003", ".py", text)` returns `[]` and the unchanged `precheck(text)` returns `("ok", [])`.
3. Measure every expected value in real FreeCAD 1.0.1 and read it back with build123d `load_step`: the volume, the bounding box, the hole count, the hole diameter and the hole positions. Never write an expected value that was not measured.
4. Write the requirement file so that it is self-contained and states the pocket size and its depth.
5. Keep the answer schema at its five keys and the required checks at the five names the other tasks use.

DO NOT: modify `evals/tasks/plate_2holes/` or `evals/tasks/plate_fillet/`. Do not change the answer schema, the scoring rule or the check names. Do not leave a `project/out/` artifact behind.

ACCEPTANCE: `uv run pytest -m "not freecad" -q` -> all pass; `uv run aturb eval evals/tasks --config aturb.local.toml` -> the new task is `ok` with score 1.0; `git status --short` lists only the six new files.

EVIDENCE: the output of both commands, the measured values, the six files.

COMMIT: `feat(evals): add a pocket task`

DEPENDS ON: T7.02.

## T7.10 — A task with a stepped boss and a fillet

GOAL: A second task a single shot can get wrong, with every expected value measured.

FILES (only these): `evals/tasks/plate_step/task.toml`, `evals/tasks/plate_step/answer.toml`, `evals/tasks/plate_step/project/expect/plt0004.toml`, `evals/tasks/plate_step/project/requirements/plt0004.md`, `evals/tasks/plate_step/project/parts/plt0004_stepped_plate.py`, `evals/tasks/plate_step/project/parts/plt0004_stepped_plate.stub`

DO EXACTLY:

1. Add the task `plate_step` for the part `plt0004`: a 120 × 60 × 5 base plate with a 60 × 60 × 3 boss centred on it, a 4 mm fillet on the four vertical corner edges of the boss, and two 10 mm through-holes at x = −40 and x = +40 on y = 0.
2. Select the fillet edges with the injected helper, by their geometry and never by an assumed index, and create the fillet feature in the part file.
3. Write the reference part so that `check_conventions("plt0004", ".py", text)` returns `[]` and the unchanged `precheck(text)` returns `("ok", [])`.
4. Measure every expected value in real FreeCAD 1.0.1 and read it back with build123d `load_step`. Never write an expected value that was not measured.
5. Write the requirement file so that it is self-contained.

DO NOT: modify the other task folders. Do not change the answer schema, the scoring rule or the check names. Do not leave a `project/out/` artifact behind.

ACCEPTANCE: `uv run pytest -m "not freecad" -q` -> all pass; `uv run aturb eval evals/tasks --config aturb.local.toml` -> the new task is `ok` with score 1.0; `git status --short` lists only the six new files.

EVIDENCE: the output of both commands, the measured values, the six files.

COMMIT: `feat(evals): add a stepped fillet task`

DEPENDS ON: T7.09.

## T7.11 — The tests of the loop

GOAL: The loop is proved, without a network and without a live model.

FILES (only these): `tests/test_agent_end_to_end.py`, `tests/test_agent_freecad.py`

DO EXACTLY:

1. Extend the stub end-to-end test with a fake client that answers with a wrong candidate first and with a correct one second, and prove that the loop repairs the task and that the attempts file holds both attempts.
2. Prove that the repair prompt of the second attempt carries the candidate-only geometry summary and no evaluator field, for both committed tasks.
3. Prove that the loop stops at the attempt limit, at the cumulative budget and on an unrepairable failure kind.
4. Add a FreeCAD test, marked `@pytest.mark.freecad`, where the candidate is wrong first and right second, the pack builds it and the task scores 1.0.
5. Use a fake or canned `ModelClient` only; no live network call and no live model.

DO NOT: use the network. Do not change the implementation. Do not change a schema. Do not mark a test as anything but `freecad`. Do not modify `evals/tasks/`.

ACCEPTANCE: `uv run pytest tests/test_agent_end_to_end.py -q` -> all pass; `uv run pytest tests/test_agent_freecad.py -q` -> all pass; `uv run pytest -m "not freecad" -q` -> all pass.

EVIDENCE: the output of all three test commands.

COMMIT: `test(agent): cover the bounded repair loop`

DEPENDS ON: T7.08, T7.09, T7.10.

## T7.12 — The Phase 7 baseline

GOAL: One measured run of the loop, written down.

FILES (only these): `docs/PHASE7_BASELINE.md`

DO EXACTLY:

1. Run the agent over the task set with the FreeCAD pack and the configured model, once, and keep the output of the command.
2. Write the date, the provider, the model, the prompt version of the first attempt, the task set, the status and the score of every task, the score of attempt 1 and of the final attempt of every task, the token counts, the cost and the exact commands, in the shape of the Phase 6 baseline.
3. State that the prompt version of the first attempt is the Phase 6 prompt version, that the later prompts carry the repair feedback, and that a model call is not deterministic.
4. If the run fails, write the failure down exactly as it happened.

DO NOT: change the implementation to make the run look better. Do not change the Phase 5 or Phase 6 baseline. Do not commit the API key or the raw response. Do not add a leaderboard or a task index.

ACCEPTANCE: `docs/PHASE7_BASELINE.md` holds the date, the model, the prompt versions, the score of every task, the score of attempt 1, the tokens, the cost and the commands.

EVIDENCE: the document, the output of the run.

COMMIT: `docs(agent): record Phase 7 baseline`

DEPENDS ON: T7.11.
