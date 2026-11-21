# Phase 6 task cards — conventions and selection helper

Proposed cards for Phase 6, derived from
[`docs/PHASE6_ROADMAP.md`](PHASE6_ROADMAP.md). The roadmap holds the scope, the
decisions and the strategy; this file holds the work. Every card is small, has
one file scope, and can be tested on its own. Phase 5 is frozen: the task
format, the five-key answer schema, the evaluator, the scoring rule, the
runner contract and the agent-run record do not change in this phase.

Rules every card inherits:

- The core stays CAD-neutral: no CAD brand name or CAD concept inside `aturb/`.
- The runner contract does not change: no new field, no new failure kind, no
  version bump.
- The helper may select, measure and assert; it never creates a feature.
- Only calls recorded in the API notes or verified in-session may be used.
- Files at most 300 lines; each card changes at most about 200 lines.
- Every chosen default is marked `# starting default`.
- One card, one commit.

## T6.01 — Selection rule and helper boundary ADR

GOAL: One decision record that states how geometry is selected and what the helper may do.

FILES (only these): `docs/adr/0007-selection-rule-and-helper-boundary.md`, `docs/adr/README.md`

DO EXACTLY:

1. Write the ADR in the style of the existing records: title, date, status, context, decision, consequences.
2. Decide that geometry is selected by what it is — orientation, vertex coordinates, geometric type, radius, position and other relevant properties — and never by an assumed positional index.
3. Decide the boundary of the helper: it may select, measure, inspect, assert and return the actual identifiers of the selected geometry; it may not create a feature, modify the feature tree or perform the engineering operation.
4. Decide that the agent keeps the engineering responsibility, that the helper lives in `packs/freecad/`, and that the precheck and its import allowlist are not weakened and the delivery mechanism is verified in T6.05.
5. Add the new record to the index in `docs/adr/README.md`.

DO NOT: change an implementation file. Do not weaken the precheck or widen its import allowlist. Do not name a tolerance or a predicate that was not measured.

ACCEPTANCE: `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK; `git diff --check` -> no output; `git status --short` lists only the two files.

EVIDENCE: the ADR file, the index line, the staged diff of the two files.

COMMIT: `docs(adr): define selection helper boundary`

DEPENDS ON: none.

## T6.02 — Project conventions document

GOAL: One document that states the conventions a part file of a project follows.

FILES (only these): `docs/CONVENTIONS.md`

DO EXACTLY:

1. Write the six project conventions of the roadmap, C1 to C6, each with the rule, the reason and a mark saying whether it can be checked from the text of a file.
2. State that the pack conventions — file contract, entry point, feature order, verified recipe of each operation — live in the prompt of the pack, because they are specific to one CAD.
3. State that the expectation file is authoritative input and that the agent may not change it without a declared reason.
4. State that the conventions are advisory: they are reported, never enforced by a refusal.

DO NOT: change the demo part, the task set, a pack prompt or an implementation file. Do not add a CAD name to a core file. Do not restate the runner contract.

ACCEPTANCE: `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK; `git diff --check` -> no output; the document names C1 to C6.

EVIDENCE: the document, the staged diff.

COMMIT: `docs: add project conventions`

DEPENDS ON: T6.01.

## T6.03 — Convention checker

GOAL: A checker that reports the conventions a candidate part file breaks, without a CAD.

FILES (only these): `aturb/agent/conventions.py`, `tests/test_agent_conventions.py`

DO EXACTLY:

1. In `aturb/agent/conventions.py` define `check_conventions(part_id, extension, text) -> list[str]`, which returns one finding per broken rule and an empty list when the file follows every rule it can check.
2. Check C1, C2, C3 and C5 only: the file name against the part ID and the extension, the marked parameter block with constants named `*_MM`, the statement of the units, and the absence of an absolute path or a drive letter.
3. Every finding names the rule it breaks and says what is wrong. A broken rule is a finding, never an exception.
4. In `tests/test_agent_conventions.py` cover a file that follows every rule, and one file per broken rule.

DO NOT: block a build. Do not change the runner contract or add a failure kind. Do not change the result record or the agent-run record. Do not name a CAD or a pack file contract.

ACCEPTANCE: `uv run pytest tests/test_agent_conventions.py -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK; `uv run python tools/size_limit.py` -> size_limit: OK.

EVIDENCE: the test output, and the findings of the committed demo part, which must be empty.

COMMIT: `feat(agent): add convention checker`

DEPENDS ON: T6.02.

## T6.04 — Convention integration into prompts

GOAL: The conventions reach the agent in the prompt.

FILES (only these): `aturb/agent/conventions.py`, `aturb/agent/prompt.py`, `tests/test_agent_conventions.py`, `tests/test_agent_prompt.py`

DO EXACTLY:

1. In `aturb/agent/conventions.py` add the text of the conventions that the prompt carries, and a function that returns it. The text names the rules C1 to C6, so the document, the checker and the prompt cannot drift apart.
2. In `aturb/agent/prompt.py` add the conventions as a sixth section of the composed prompt, after the pack prompt and before the requirement, and keep the order of the other five sections.
3. The prompt version changes with the text, and the tests show that it changes when the conventions change.
4. In `tests/test_agent_prompt.py` cover the new section, its place in the order and the new prompt version.

DO NOT: change the core instruction, the output contract or the fence handling. Do not change the agent-run record. Do not put a CAD name in the core.

ACCEPTANCE: `uv run pytest tests/test_agent_prompt.py tests/test_agent_conventions.py -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK; `uv run python tools/size_limit.py` -> size_limit: OK.

EVIDENCE: the test output, the new prompt version of the committed task.

COMMIT: `feat(agent): carry conventions in the prompt`

DEPENDS ON: T6.03.

## T6.05 — Safe helper-delivery spike

GOAL: Find out, in the real CAD, how a helper module can reach the part file without weakening the precheck.

FILES (only these): `tools/spikes/fc_helper_delivery.py`, `docs/api_notes/freecad.md`

DO EXACTLY:

1. Write a spike that tries the three candidate mechanisms of the roadmap inside the CAD: the harness loads the helper and puts it where the part file reaches it without an import; the helper is copied into the project and loaded by path; the helper is exposed through the document.
2. Run it and keep the output. Record in the API notes which mechanism works, with the exact calls and the observed output, and the task ID of the row.
3. If no mechanism is safe, record that in the API notes and stop the phase with a report. Do not make a mechanism work by weakening a check.

DO NOT: change the precheck or its import allowlist. Do not change the runner, the harness or any other product file. Do not commit a helper that creates a feature. Do not guess a FreeCAD call.

ACCEPTANCE: the spike runs and prints the result of every mechanism it tried; `docs/api_notes/freecad.md` holds a row for the mechanism that works; `uv run ruff check tools/spikes/fc_helper_delivery.py` -> All checks passed!.

EVIDENCE: the output of the spike, the new rows of the API notes.

COMMIT: `docs(freecad): record helper delivery spike`

DEPENDS ON: T6.01. May run in parallel with T6.02, T6.03 and T6.04.

## T6.06 — FreeCAD selection helper

GOAL: A helper in the FreeCAD pack that selects edges and faces by their geometric properties.

FILES (only these): `packs/freecad/helper/__init__.py`, `packs/freecad/helper/select.py`, `tests/packs/test_fc_select.py`

DO EXACTLY:

1. Implement the selection by geometric property — orientation, vertex coordinates, geometric type, radius, position — using only the calls recorded in the API notes, and record every new call in the notes with the task ID.
2. Return the actual identifiers and names of the selected geometry, so the agent can use them in the code it writes.
3. Assert the number of selected items and their properties, and report the assertion when it does not hold.
4. Measure and inspect geometry as well, and keep the module under 300 lines.
5. In `tests/packs/test_fc_select.py` cover the selection of the vertical corner edges of the demo plate, the selection of a circular edge by its radius, and the assertion that fails when nothing matches.

DO NOT: create a feature of any kind. Do not modify the feature tree. Do not select by an assumed positional index. Do not import the core. Do not use a call the API notes do not record. Do not widen the precheck.

ACCEPTANCE: `uv run pytest tests/packs/test_fc_select.py -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK; `uv run python tools/size_limit.py` -> size_limit: OK.

EVIDENCE: the test output, the API note rows of the calls the helper uses.

COMMIT: `feat(freecad): add geometry selection helper`

DEPENDS ON: T6.05.

## T6.07 — Safe harness integration

GOAL: The helper reaches the part file in the real build, by the mechanism T6.05 measured.

FILES (only these): `packs/freecad/harness/build_part.py`, `tests/packs/test_harness_isolation.py`, `tests/packs/test_fc_precheck.py`

DO EXACTLY:

1. Load the helper in the harness by the mechanism T6.05 measured, and make it reachable to the part file in the same way the spike proved.
2. Keep the precheck and its import allowlist exactly as they are, and keep the environment of the child process minimal.
3. Prove in the tests that a part file that uses the helper builds, and that a part file that tries to reach anything else is still refused by the precheck.
4. Prove that the helper is not reachable from the core and that the core does not import the pack.

DO NOT: change the precheck or its import allowlist. Do not add an environment variable that carries code. Do not change the runner contract or add a failure kind. Do not change the result record.

ACCEPTANCE: `uv run pytest tests/packs -q` -> all pass; `uv run pytest -m "not freecad" -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

EVIDENCE: the test output, and the precheck file unchanged in the diff.

COMMIT: `feat(freecad): deliver selection helper to part files`

DEPENDS ON: T6.06.

## T6.08 — Helper prompt documentation

GOAL: The pack prompt tells the agent what the helper offers and what it does not.

FILES (only these): `packs/freecad/prompt/agent.md`, `packs/freecad/prompt/README.md`, `tests/test_agent_prompt_files.py`

DO EXACTLY:

1. Document the helper in the pack prompt: the calls it offers, the task IDs of the API note rows that verified them, and the identifiers it returns.
2. State that the helper selects, measures and asserts, and that it never creates a feature; the agent still creates the feature and sets its parameters.
3. State that the selection is by geometric property and never by an assumed index.
4. In `tests/test_agent_prompt_files.py` cover that every task ID the prompt cites exists in the API notes, and that the prompt states the boundary of the helper.

DO NOT: name a call the API notes do not record. Do not put a helper in `aturb/`. Do not change the file contract, the core instruction or the output contract.

ACCEPTANCE: `uv run pytest tests/test_agent_prompt_files.py -q` -> all pass; `uv run ruff check .` -> All checks passed!.

EVIDENCE: the test output, the diff of the pack prompt.

COMMIT: `docs(freecad): document selection helper in pack prompt`

DEPENDS ON: T6.06, T6.07.

## T6.09 — Second evaluation task requiring fillet selection

GOAL: A second task that needs the agent to select existing edges.

FILES (only these): `evals/tasks/plate_fillet/task.toml`, `evals/tasks/plate_fillet/answer.toml`, `evals/tasks/plate_fillet/project/parts/plt0002_base_plate_fillet.py`, `evals/tasks/plate_fillet/project/parts/plt0002_base_plate_fillet.stub`, `evals/tasks/plate_fillet/project/expect/plt0002.toml`, `evals/tasks/plate_fillet/project/requirements/plt0002.md`

DO EXACTLY:

1. Create the task with the existing format: the task ID is the folder name, the part ID is `plt0002`, and the answer file holds exactly the five keys of the answer schema.
2. The reference part is the demo plate with a 3 mm fillet on the four vertical corner edges, built with the calls recorded in the API notes, and the stub file is the matching stub.
3. The expectation file holds all five expected values. The volume is the one measured in T1.25, 35175.973506 mm³, and the card verifies it by building the reference part before the values are written down.
4. The requirements file asks for the fillet in plain language, the way the requirement of the first task does.

DO NOT: change the answer schema, the result record or the existing task. Do not add a sixth key. Do not change the scoring rule. Do not write an expected value that was not measured.

ACCEPTANCE: `uv run pytest tests/test_evals_task.py tests/test_evals_answer.py -q` -> all pass; `uv run aturb eval evals/tasks --config aturb.local.toml` -> the new task scores 1.0; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

EVIDENCE: the output of the evaluation, the measured volume of the reference part.

COMMIT: `feat(evals): add fillet selection task`

DEPENDS ON: T6.02.

## T6.10 — Agent testing with conventions and selection

GOAL: The agent path with the conventions and the helper, proven without a CAD and with the CAD.

FILES (only these): `tests/test_agent_end_to_end.py`, `tests/test_agent_freecad.py`

DO EXACTLY:

1. Extend the stub end-to-end test so that the prompt of the run carries the conventions, and that the candidate of the test follows them.
2. Add a FreeCAD test in which the candidate uses the helper to select the edges of a fillet, the pack builds it, the neutral checks run over the exported STEP and the task scores 1.0.
3. Prove that the committed task set is unchanged after the run, and that the helper is not reachable from the core.

DO NOT: use the network. Do not change the implementation. Do not change a schema. Do not mark a test as anything but `freecad`.

ACCEPTANCE: `uv run pytest tests/test_agent_end_to_end.py -q` -> all pass; `uv run pytest tests/test_agent_freecad.py -q` -> all pass; `uv run pytest -m "not freecad" -q` -> all pass.

EVIDENCE: the output of both test files.

COMMIT: `test(agent): cover conventions and selection`

DEPENDS ON: T6.04, T6.07, T6.08, T6.09.

## T6.11 — Phase 6 baseline measurement

GOAL: One measured run of the agent with the conventions and the helper, written down.

FILES (only these): `docs/PHASE6_BASELINE.md`

DO EXACTLY:

1. Run the agent over the task set with the FreeCAD pack and the configured model, and keep the output of the command.
2. Write the date, the provider, the model, the prompt version, the task set, the status and the score of every task, the token counts, the cost and the exact commands, in the shape of the Phase 5 baseline.
3. State that the prompt version differs from the Phase 5 baseline, because the conventions were added to the prompt, and that a model call is not deterministic.
4. If the run fails, write the failure down exactly as it happened.

DO NOT: change the implementation to make the run look better. Do not change the Phase 5 baseline. Do not commit the API key or the raw response. Do not add a leaderboard or a task index.

ACCEPTANCE: `docs/PHASE6_BASELINE.md` holds the date, the model, the prompt version, the score of every task, the tokens, the cost and the commands.

EVIDENCE: the document, the output of the run.

COMMIT: `docs(agent): record Phase 6 baseline`

DEPENDS ON: T6.10.

## T6.12 — Phase acceptance

GOAL: Prove the phase is green and that nothing outside it moved.

FILES (only these): none; this card only runs commands and reports.

DO EXACTLY:

1. Run the full acceptance list: `uv run pytest -m "not freecad" -q`, `uv run pytest -q`, `uv run ruff check .`, `uv run python tools/size_limit.py`, `uv run python tools/agnostic_lint.py`.
2. Run `git status --short --untracked-files=all` and `git diff --stat` and check that the changed files are the ones the cards listed.
3. Confirm that the runner contract, the answer schema, the result record and the agent-run record are unchanged, and that the precheck and its import allowlist are unchanged.
4. Report the output of every command.

DO NOT: change a file to make a command pass.

ACCEPTANCE: every acceptance command passes; the report lists the changed files.

EVIDENCE: the output of every command, the list of the changed files.

COMMIT: none; the orchestrator closes the phase.

DEPENDS ON: T6.11.
