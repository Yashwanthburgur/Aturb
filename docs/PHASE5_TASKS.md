# Phase 5 task cards — stock-agent baseline

Proposed cards for Phase 5, derived from
[`docs/PHASE5_ROADMAP.md`](PHASE5_ROADMAP.md). The roadmap holds the scope and
the decisions; this file holds the work. Every card is small, has one file
scope, and can be tested on its own. Phase 4 is frozen: the task format, the
five-key answer schema, the evaluator, the scoring rule and the runner
contract do not change in this phase.

## T5.01 — The agent boundary types

GOAL: The types the agent boundary is made of, with no behaviour and no I/O.

FILES (only these): `aturb/agent/__init__.py`, `aturb/agent/types.py`, `tests/test_agent_types.py`

DO EXACTLY:

1. Create `aturb/agent/` with an `__init__.py` holding one line of docstring.
2. In `aturb/agent/types.py` define the frozen dataclasses `ModelRequest` (`prompt`, `model`, `max_output_tokens`), `ModelResponse` (`text`, `input_tokens`, `output_tokens`) and `AgentRun` (`task_id`, `part_id`, `provider`, `model`, `prompt_version`, `input_tokens`, `output_tokens`, `cost_usd`, `attempts`, `status`, `error`), the `ModelClient` protocol with one method `complete(request)`, and the `AgentError` exception.
3. `AgentRun.__post_init__` rejects a status outside `ok`/`error`, a negative token count, attempts or cost, and an error text on an `ok` run. `to_dict()` returns exactly the eleven fields.
4. In `tests/test_agent_types.py` cover a valid `ok` run, a valid `error` run, every rejected value, the exact keys of `to_dict()` and that the dataclasses are frozen.

DO NOT: add a method that reads a file, opens a socket or names a CAD system.

ACCEPTANCE: `uv run pytest tests/test_agent_types.py -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

DEPENDS ON: none.

## T5.02 — Prompt composition and versioning

GOAL: One function that builds the prompt, and one that names it.

FILES (only these): `aturb/agent/prompt.py`, `tests/test_agent_prompt.py`

DO EXACTLY:

1. In `aturb/agent/prompt.py` define `CORE_INSTRUCTION`, a short fixed block that asks for one part file and nothing else, naming no CAD system and no library.
2. Define `compose_prompt(pack_prompt, requirement, expectations) -> str` that joins, in this order and with a blank line between them: the core instruction, the pack prompt, the requirement, the expectations and the output contract. It raises `ValueError` when the pack prompt or the requirement is empty.
3. Define `prompt_version(text) -> str`, the first 16 hex characters of the SHA-256 of the text, and `strip_code_fence(text) -> str`, which removes one leading and one trailing markdown fence when the text has them and returns the text unchanged otherwise.
4. In `tests/test_agent_prompt.py` cover the order of the parts, the rejection of an empty part, that the version is 16 hex characters, that it changes when the text changes and does not when the text does not, and the fence handling for fenced, unfenced and empty text.

DO NOT: parse the model output beyond the one fence. Do not put a CAD name, a library name or a task name in the core instruction.

ACCEPTANCE: `uv run pytest tests/test_agent_prompt.py -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

DEPENDS ON: T5.01.

## T5.03 — Verify the model API and record it

GOAL: The exact shape of the model request and response, verified in-session and written down before any client code exists.

FILES (only these): `docs/api_notes/model.md`, `tools/spikes/model_call.py`, `.gitignore`

DO EXACTLY:

1. Create `tools/spikes/model_call.py`. It reads the endpoint, the model and the key from the environment variables named in the local configuration, makes one call with a short prompt, and prints the request it sent and the response it got, with the key redacted.
2. Run it once against the configured provider. If the call fails, report the failure exactly and stop; do not guess the shape of the API.
3. Create `docs/api_notes/model.md` in the style of [`docs/api_notes/freecad.md`](api_notes/freecad.md): one row per verified fact, with the task ID that verified it. It states the endpoint path, the request body fields, the response fields that carry the text and the token usage, and the shape of an error response.
4. State in the file that only the rows below were actually executed.
5. Add `.env` to [`.gitignore`](../.gitignore), so the local file that holds the key is never committed.

DO NOT: put the API key in the repository, in the spike or in the notes. Do not add a dependency. Do not write client code in this card.

ACCEPTANCE: the spike runs and prints a request and a response; `docs/api_notes/model.md` holds a row for the request body, the response text and the token usage; `uv run ruff check tools/spikes/model_call.py` -> All checks passed!.

DEPENDS ON: none. May run in parallel with T5.01 and T5.02.

## T5.04 — The model client

GOAL: One client that makes the call recorded in the API notes, and nothing else.

FILES (only these): `aturb/agent/model.py`, `tests/test_agent_model.py`

DO EXACTLY:

1. In `aturb/agent/model.py` define `HttpModelClient`, built on `urllib.request` from the standard library. It takes the base URL, the model, the API key, the timeout and a `transport` callable.
2. The default transport sends the request body recorded in [`docs/api_notes/model.md`](api_notes/model.md) and returns the response text. The transport is a parameter so the tests never touch the network.
3. The client reads only the fields recorded in the API notes. A response that does not hold them raises `AgentError`.
4. A non-success status, a timeout and a transport failure all raise `AgentError` with a message that says what went wrong. The API key never appears in the message.
5. In `tests/test_agent_model.py` cover, with a fake transport: a good response, a response without the text field, a response without the token usage, a non-success status, a transport failure, and that the key is in no error message.

DO NOT: add a dependency. Do not retry. Do not parse fields the API notes do not record. Do not name a CAD system.

ACCEPTANCE: `uv run pytest tests/test_agent_model.py -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK; `uv run python tools/size_limit.py` -> size_limit: OK.

DEPENDS ON: T5.01, T5.03.

## T5.05 — Agent configuration

GOAL: The settings of the agent, read from the configuration, with the key outside the configuration.

FILES (only these): `aturb/agent/config.py`, `tests/test_agent_config.py`, `aturb.example.toml`

DO EXACTLY:

1. In `aturb/agent/config.py` define `agent_settings(cfg) -> dict` that reads the `agent` section and returns the settings with the defaults filled in: `provider`, `model`, `base_url`, `api_key_env`, `max_input_tokens`, `max_output_tokens`, `max_cost_usd`, `input_price_per_mtok`, `output_price_per_mtok`, `timeout_s`. Every default is marked `# starting default` in the source.
2. Define `read_api_key(settings, env) -> str` that reads the key from the environment variable named by `api_key_env` and raises `AgentError` when the variable is not set or empty. The key is never read from the configuration.
3. Add an `[agent]` section to `aturb.example.toml` with the same keys and empty or placeholder values. The section must not hold a key.
4. In `tests/test_agent_config.py` cover the defaults, an override of every key, a missing section, a key read from the environment and a missing environment variable.

DO NOT: add the key to the configuration file or to the example file. Do not change [`aturb/config.py`](../aturb/config.py) or the `[packs]` section.

ACCEPTANCE: `uv run pytest tests/test_agent_config.py -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

DEPENDS ON: T5.01.

## T5.06 — The candidate workspace

GOAL: A scratch task folder that holds the task, holds no reference part, and receives the candidate.

FILES (only these): `aturb/agent/workspace.py`, `tests/test_agent_workspace.py`

DO EXACTLY:

1. In `aturb/agent/workspace.py` define `prepare_candidate_task(task_dir, work_dir) -> Path`, which creates `work_dir/<task_id>/` and copies `task.toml`, `answer.toml` and the project folders `expect/` and `requirements/` into it, creates an empty `project/parts/` and returns the path of the scratch task folder.
2. Define `candidate_path(project, part_id, extension) -> Path`, which returns `project/parts/<part_id>_candidate<extension>`, and `write_candidate(project, part_id, extension, text) -> Path`, which writes the text and returns the path.
3. The copy never includes `project/parts/` and never includes `project/out/`, so the reference part file of the committed task is not in the scratch folder. Every path stays inside the work directory; a path that escapes raises `ValueError`.
4. In `tests/test_agent_workspace.py` cover, using the committed task: the scratch folder holds `task.toml`, `answer.toml`, `expect/` and `requirements/`; it holds no part file; the candidate path ends with `_candidate` and the given extension; the written file holds the text; and the committed task folder is unchanged after the copy.

DO NOT: copy the reference part file. Do not write into the committed task folder. Do not change [`aturb/evals/runner.py`](../aturb/evals/runner.py).

ACCEPTANCE: `uv run pytest tests/test_agent_workspace.py -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK.

DEPENDS ON: T5.01.

## T5.07 — The pack prompt files

GOAL: The instructions of each pack, owned by the pack and read as text.

FILES (only these): `packs/freecad/prompt/agent.md`, `packs/stub/prompt/agent.md`, `packs/stub/prompt/README.md`, `tests/test_agent_prompt_files.py`

DO EXACTLY:

1. Create `packs/freecad/prompt/agent.md`. It states the file contract of the pack's language, the verified API calls the agent may use, and the output contract. Every API call it names cites the task ID of its row in [`docs/api_notes/freecad.md`](../docs/api_notes/freecad.md).
2. Create `packs/stub/prompt/agent.md` with the minimal instruction for the stub language, so the agent path can be tested without a CAD, and update `packs/stub/prompt/README.md` to say that the stub pack has a minimal agent prompt.
3. In `tests/test_agent_prompt_files.py` cover: every pack that declares a `prompt_dir` has an `agent.md` in it; every task ID cited in a pack prompt exists in the matching API note; and the FreeCAD prompt names the file contract and the output contract.

DO NOT: put a prompt in `aturb/`. Do not name an API call the API notes do not record. Do not change the pack manifests.

ACCEPTANCE: `uv run pytest tests/test_agent_prompt_files.py -q` -> all pass; `uv run ruff check .` -> All checks passed!.

DEPENDS ON: T5.01.

## T5.08 — The agent run

GOAL: One task, one model call, one candidate file, one agent run.

FILES (only these): `aturb/agent/run.py`, `tests/test_agent_run.py`

DO EXACTLY:

1. In `aturb/agent/run.py` define `run_agent(task_dir, client, settings, pack, work_dir) -> AgentRun`.
2. The run reads the task file, the requirement file, the expectation file and the pack prompt, composes the prompt, checks the input token cap, calls the client once, strips the fence, writes the candidate into the scratch project and returns the agent run.
3. The prompt version is the hash of the exact text sent to the model. The token counts are the ones the provider reported. The cost is computed from the configured prices and is `0.0` when no price is configured.
4. The budget is checked before the call. A prompt over `max_input_tokens` or a call that would pass `max_cost_usd` is refused without calling the model.
5. Every failure is an agent run with `status = "error"` and an error text, never an exception: a missing requirement file, a missing pack prompt, a refused budget, a failed call and an empty answer. `attempts` is `1` in every run of this phase.
6. In `tests/test_agent_run.py` cover, with a fake client: a good run that writes the candidate and reports the tokens; the prompt version; the cost with and without a configured price; the refused budget; the failed call; the empty answer; and that the client was called exactly once.

DO NOT: retry. Do not call the model twice. Do not read the reference part file. Do not change the Phase 4 modules.

ACCEPTANCE: `uv run pytest tests/test_agent_run.py -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK; `uv run python tools/size_limit.py` -> size_limit: OK.

DEPENDS ON: T5.02, T5.04, T5.05, T5.06, T5.07.

## T5.09 — The agent-run record file

GOAL: The agent runs of one run, written to a dated file of their own.

FILES (only these): `aturb/agent/record.py`, `tests/test_agent_record.py`

DO EXACTLY:

1. In `aturb/agent/record.py` define `write_agent_runs(results_dir, runs) -> Path` and `read_agent_runs(path) -> list[AgentRun]`.
2. The file is named `<YYYY-MM-DD>_<HHMMSS>_agent.toml` and sits in the results folder, next to the result file of the same run. One `[[runs]]` record per agent run, in order, with exactly the eleven fields of the agent run.
3. The file is written by hand, with the same string escaping rules as [`aturb/evals/report.py`](../aturb/evals/report.py). The Phase 4 module is frozen and is not changed; the small escaper is repeated here.
4. `read_agent_runs` turns the records back into agent runs. A file that is not valid TOML, and a record that does not hold the eleven fields, raise `ValueError`.
5. In `tests/test_agent_record.py` cover one record per run, the file name shape, an error run that keeps its task ID and its error text, reading the file back into runs equal to the originals, and a record with a missing field.

DO NOT: change [`aturb/evals/report.py`](../aturb/evals/report.py) or the Phase 4 result file. Do not add a field to the agent run. Do not add a dependency.

ACCEPTANCE: `uv run pytest tests/test_agent_record.py -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/size_limit.py` -> size_limit: OK.

DEPENDS ON: T5.01, T5.08.

## T5.10 — The CLI flag

GOAL: `aturb eval --agent` runs the agent over a task set and scores it with the existing pipeline.

FILES (only these): `aturb/cli.py`, `tests/test_cli.py`

DO EXACTLY:

1. Add the flag `--agent` to the `eval` subcommand. It is off by default, and without it the command behaves exactly as it does today; the existing CLI tests must pass unchanged.
2. With the flag, for every task folder of the set: prepare the scratch task folder, run the agent, and score the candidate with the existing [`run_task()`](../aturb/evals/runner.py). The result file is written by the existing [`write_results()`](../aturb/evals/report.py) and keeps its format.
3. The agent runs of the run are written with [`write_agent_runs()`](../aturb/agent/record.py) into the same results folder.
4. The exit codes do not change: `0` when every task is `ok`, `1` when any task is `failed` or `error`, `2` for a configuration or pack error.
5. In `tests/test_cli.py` cover, with the stub pack and a fake client: a good task set returns `0` and prints the summary; a malformed task set returns `1` and still prints a line for that task; the result file and the agent file are both written; and the command without the flag is unchanged.

DO NOT: change the output of `build` or `check`. Do not change the result file format. Do not add a new subcommand. Do not call a model in the tests.

ACCEPTANCE: `uv run pytest tests/test_cli.py -q` -> all pass; `uv run ruff check .` -> All checks passed!; `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK; `uv run python tools/size_limit.py` -> size_limit: OK.

DEPENDS ON: T5.08, T5.09.

## T5.11 — The agent path without a CAD

GOAL: The whole path, from the prompt to the score, proven without a CAD and without a network.

FILES (only these): `tests/test_agent_end_to_end.py`

DO EXACTLY:

1. Write one test that runs the agent over the committed task set with the stub pack and a fake client that returns a canned candidate. The stub pack builds it, the neutral checks run over the exported STEP and the task scores `1.0`.
2. Write one test that the agent run file holds one record per task, with the model, the prompt version, the token counts and the cost.
3. Write one test that the committed task folder is unchanged after the run: the same files, and no candidate file in it.
4. Write one test that a client which fails gives an error run and an error task result, and that the run does not stop the other tasks.

DO NOT: use the network. Do not use FreeCAD. Do not change the implementation.

ACCEPTANCE: `uv run pytest tests/test_agent_end_to_end.py -q` -> all pass; `uv run pytest -m "not freecad" -q` -> all pass.

DEPENDS ON: T5.10.

## T5.12 — The agent path with FreeCAD

GOAL: The same path, proven with the real CAD.

FILES (only these): `tests/test_agent_freecad.py`

DO EXACTLY:

1. Write one test marked `@pytest.mark.freecad` that runs the agent over the committed task with the FreeCAD pack and a fake client that returns a canned candidate part file. The pack builds it, the checks run over the exported STEP and the task scores `1.0`.
2. Write one test marked `@pytest.mark.freecad` that a candidate the pack refuses gives an error task result and an error text that says why.
3. The tests use the local configuration the way [`tests/test_demo_plate.py`](../tests/test_demo_plate.py) does.

DO NOT: use the network. Do not change the implementation. Do not mark the tests as anything but `freecad`.

ACCEPTANCE: `uv run pytest tests/test_agent_freecad.py -q` -> all pass; `uv run pytest -q` -> all pass.

DEPENDS ON: T5.11.

## T5.13 — The baseline run

GOAL: One measured run of the stock agent on the committed task set, written down.

FILES (only these): `docs/PHASE5_BASELINE.md`

DO EXACTLY:

1. Run the agent over the committed task set with the FreeCAD pack and the configured model, and keep the output of the command.
2. Write `docs/PHASE5_BASELINE.md` with the date, the provider, the model, the prompt version, the task set, the status and the score of every task, the token counts, the cost, and the exact commands that produced the run.
3. State plainly that a model call is not deterministic, so the baseline is a recorded measurement and not a function that can be replayed exactly.
4. If the run fails, write down the failure exactly as it happened. Do not change the implementation to make the baseline look better.

DO NOT: add a leaderboard, a task index or a second task. Do not change the implementation. Do not commit the API key or the raw response.

ACCEPTANCE: `docs/PHASE5_BASELINE.md` holds the date, the model, the prompt version, the score of every task, the tokens, the cost and the commands.

DEPENDS ON: T5.12.

## T5.14 — Phase 5 acceptance

GOAL: Prove the phase is green and that nothing outside it moved.

FILES (only these): none; this card only runs commands and reports.

DO EXACTLY:

1. Run the full acceptance list: `uv run pytest -m "not freecad" -q`, `uv run pytest -q`, `uv run ruff check .`, `uv run python tools/size_limit.py`, `uv run python tools/agnostic_lint.py`.
2. Run `git status --short --untracked-files=all` and `git diff --stat` and check that the changed files are the ones the cards listed.
3. Report the output of every command.

DO NOT: change a file to make a command pass.

ACCEPTANCE: every acceptance command passes; the report lists the changed files.

NOTE: acceptance found one defect on the path of a malformed agent configuration: the error was raised outside the guard that turns it into exit code 2. The fix landed in its own commit, `623a928 fix(cli): handle malformed agent configuration`, which changed [`aturb/cli.py`](../aturb/cli.py) and [`tests/test_cli.py`](../tests/test_cli.py). The card itself changed no file.

DEPENDS ON: T5.13.
