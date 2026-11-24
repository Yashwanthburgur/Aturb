"""Tests for the bounded repair loop of the agent, with a fake client and no network."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aturb.agent.config import agent_settings
from aturb.agent.loop import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_TOTAL_COST_USD,
    DEFAULT_MAX_TOTAL_INPUT_TOKENS,
    DEFAULT_MAX_TOTAL_OUTPUT_TOKENS,
    UNREPAIRABLE_FAILURE_KINDS,
    LoopResult,
    run_agent_loop,
)
from aturb.agent.prompt import prompt_version
from aturb.agent.run import run_agent
from aturb.agent.types import AgentError, ModelRequest, ModelResponse
from aturb.packs import load_manifest, load_runner

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"
PACKS_ROOT = REPO_ROOT / "packs"
STUB_PACK = load_manifest(PACKS_ROOT / "stub" / "pack.toml")
TASK_ID = "plate_2holes"
GOOD = "# the candidate part\n"
SENTINEL = "35214.602"
CHECK_NAMES = ("volume", "bbox_x", "bbox_y", "bbox_z", "hole_count")


class _FakeClient:
    """A client that records the requests and answers with a canned list."""

    def __init__(self, answers: list[str] | None = None, input_tokens: int = 120,
                 output_tokens: int = 45) -> None:
        """Take the answers the client gives, one per call."""
        self.answers = list(answers) if answers else [GOOD]
        self.input_tokens, self.output_tokens = input_tokens, output_tokens
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Record the request and answer with the next canned answer."""
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.answers) - 1)
        return ModelResponse(text=self.answers[index], input_tokens=self.input_tokens,
                             output_tokens=self.output_tokens)


class _FailingClient(_FakeClient):
    """A client whose call always fails."""

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Record the request and fail."""
        self.requests.append(request)
        raise AgentError("the provider refused the call")


class _FailingSecondClient(_FakeClient):
    """A client that answers the first call and fails on the next one."""

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Answer once, then fail."""
        if self.requests:
            raise AgentError("the provider refused the call")
        return super().complete(request)


def _settings(**overrides) -> dict:
    """Return the agent settings of the tests."""
    return {**agent_settings({}), **overrides}


def _loop(tmp_path: Path, client, task: Path = TASK_DIR, **overrides) -> LoopResult:
    """Run the loop over a task with the runner of the stub pack."""
    runner = load_runner("stub", {"packs": {}}, PACKS_ROOT)
    return run_agent_loop(task, client, runner, _settings(**overrides),
                          STUB_PACK, tmp_path, timeout_s=60)


def _task_with_a_wrong_volume(tmp_path: Path) -> Path:
    """Return a copy of the committed task whose expected volume is wrong."""
    task = tmp_path / "task" / TASK_ID
    shutil.copytree(TASK_DIR, task)
    expect = task / "project" / "expect" / "plt0001.toml"
    expect.write_text(expect.read_text(encoding="utf-8").replace(
        "volume = 35214.602", "volume = 30000.0"), encoding="utf-8")
    return task


def _files(folder: Path) -> set[str]:
    """Return the relative paths of every file under a folder."""
    return {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()}


def test_the_starting_defaults_are_the_documented_ones():
    """The defaults of the loop are the ones the card names."""
    assert DEFAULT_MAX_ATTEMPTS == 3
    assert DEFAULT_MAX_TOTAL_INPUT_TOKENS == 60_000
    assert DEFAULT_MAX_TOTAL_OUTPUT_TOKENS == 24_000
    assert DEFAULT_MAX_TOTAL_COST_USD == 0.75
    assert UNREPAIRABLE_FAILURE_KINDS == frozenset({"runner_crash", "input_error"})


def test_the_first_attempt_passes(tmp_path):
    """A candidate that passes stops the loop after one call."""
    client = _FakeClient()
    loop = _loop(tmp_path, client)
    assert loop.stop_reason == "passed"
    assert loop.run.status == "ok"
    assert loop.run.attempts == 1
    assert len(client.requests) == 1
    assert loop.result.score == 1.0
    assert len(loop.attempts) == 1
    assert loop.attempts[0].attempt == 1
    assert loop.attempts[0].outcome == "passed"
    assert "## Repair" not in client.requests[0].prompt


def test_a_repair_can_pass_on_the_second_attempt(tmp_path):
    """A repair that passes gives two calls and the sums of the two attempts."""
    client = _FakeClient(["# STUB: fail=syntax_error\n", GOOD])
    loop = _loop(tmp_path, client)
    assert loop.stop_reason == "passed"
    assert len(client.requests) == 2
    assert loop.run.attempts == 2
    assert loop.run.input_tokens == 240
    assert loop.run.output_tokens == 90
    assert loop.run.prompt_version == prompt_version(client.requests[0].prompt)
    assert loop.result.score == 1.0
    assert len(loop.attempts) == 2
    assert loop.attempts[0].outcome == "build_failed:syntax_error"
    assert loop.attempts[1].attempt == 2


def test_the_repair_prompt_carries_no_evaluator_value(tmp_path):
    """The repair prompt holds no expected value and no check name (ADR-0008)."""
    client = _FakeClient(["# STUB: fail=syntax_error\n", GOOD])
    _loop(tmp_path, client)
    repair = client.requests[1].prompt
    assert "## Repair" in repair
    assert SENTINEL not in repair
    for name in CHECK_NAMES:
        assert name not in repair


def test_the_repair_prompt_carries_the_previous_candidate(tmp_path):
    """The repair prompt carries the source code of the previous candidate."""
    client = _FakeClient(["# STUB: fail=syntax_error\n", GOOD])
    _loop(tmp_path, client)
    first, repair = client.requests[0].prompt, client.requests[1].prompt
    assert "## Repair" not in first
    assert "Previous candidate:" in repair
    assert repair.index("# STUB: fail=syntax_error") > repair.index("Previous candidate:")
    assert SENTINEL not in first
    for name in CHECK_NAMES:
        assert name not in first


def test_the_loop_stops_at_the_attempt_limit(tmp_path):
    """The loop stops when the attempt limit is reached."""
    client = _FakeClient(["# STUB: fail=syntax_error\n"])
    loop = _loop(tmp_path, client, max_attempts=2)
    assert loop.stop_reason == "max_attempts"
    assert len(client.requests) == 2
    assert loop.run.attempts == 2
    assert len(loop.attempts) == 2
    assert loop.result.status == "error"
    assert "syntax_error" in loop.result.error


def test_the_loop_stops_before_the_model_when_the_token_budget_is_passed(tmp_path):
    """The cumulative token budget stops the loop before the next call."""
    client = _FakeClient(["# STUB: fail=syntax_error\n"])
    loop = _loop(tmp_path, client, max_output_tokens=512, max_total_output_tokens=512)
    assert loop.stop_reason == "budget_exceeded"
    assert len(client.requests) == 1
    assert loop.run.attempts == 1
    assert "budget" in loop.attempts[-1].error
    assert loop.attempts[-1].outcome == "budget_exceeded"
    assert loop.result.status == "error"
    assert "syntax_error" in loop.result.error


def test_the_loop_stops_before_the_model_when_the_cost_budget_is_passed(tmp_path):
    """The cumulative cost budget stops the loop before the next call."""
    client = _FakeClient(["# STUB: fail=syntax_error\n"])
    loop = _loop(tmp_path, client, max_output_tokens=512, output_price_per_mtok=1_000_000.0,
                 max_cost_usd=1000.0, max_total_cost_usd=530.0)
    assert loop.stop_reason == "budget_exceeded"
    assert len(client.requests) == 1
    assert "cost" in loop.attempts[-1].error
    assert loop.result.status == "error"
    assert "syntax_error" in loop.result.error


def test_the_last_judged_result_survives_a_budget_refusal(tmp_path):
    """A budget refusal after a judged attempt keeps the judged result (D10)."""
    task = _task_with_a_wrong_volume(tmp_path)
    client = _FakeClient()
    loop = _loop(tmp_path, client, task=task, max_output_tokens=512, max_total_output_tokens=512)
    assert len(client.requests) == 1
    assert loop.stop_reason == "budget_exceeded"
    assert loop.result.status == "failed"
    assert loop.result.score == 0.8
    assert loop.attempts[-1].outcome == "budget_exceeded"
    assert "budget" in loop.attempts[-1].error


def test_the_last_judged_result_survives_a_model_error(tmp_path):
    """A model error after a judged attempt keeps the judged result (D10)."""
    task = _task_with_a_wrong_volume(tmp_path)
    client = _FailingSecondClient()
    loop = _loop(tmp_path, client, task=task)
    assert loop.stop_reason == "model_error"
    assert loop.result.status == "failed"
    assert loop.result.score == 0.8
    assert loop.attempts[-1].outcome == "model_error"


@pytest.mark.parametrize("kind", ["runner_crash", "input_error"])
def test_the_loop_stops_on_an_unrepairable_failure_kind(tmp_path, kind):
    """A failure kind that cannot be repaired stops the loop at once."""
    client = _FakeClient([f"# STUB: fail={kind}\n"])
    loop = _loop(tmp_path, client)
    assert loop.stop_reason == "unrepairable"
    assert len(client.requests) == 1
    assert loop.attempts[0].outcome == f"build_failed:{kind}"
    assert kind in UNREPAIRABLE_FAILURE_KINDS


@pytest.mark.parametrize("kind", ["syntax_error", "runtime_error", "invalid_geometry"])
def test_the_loop_retries_a_repairable_failure_kind(tmp_path, kind):
    """A failure kind that can be repaired gives the model another chance."""
    client = _FakeClient([f"# STUB: fail={kind}\n", GOOD])
    loop = _loop(tmp_path, client)
    assert len(client.requests) == 2
    assert loop.stop_reason == "passed"
    assert loop.attempts[0].outcome == f"build_failed:{kind}"


def test_the_loop_stops_when_the_model_call_fails(tmp_path):
    """A failed model call stops the loop at once."""
    client = _FailingClient()
    loop = _loop(tmp_path, client)
    assert loop.stop_reason == "model_error"
    assert len(client.requests) == 1
    assert loop.run.status == "error"
    assert "the model call failed" in loop.run.error
    assert loop.run.attempts == 1


def test_the_loop_stops_when_the_answer_is_empty(tmp_path):
    """An empty answer stops the loop at once."""
    client = _FakeClient([""])
    loop = _loop(tmp_path, client)
    assert loop.stop_reason == "model_error"
    assert len(client.requests) == 1
    assert "empty" in loop.run.error


def test_one_attempt_reproduces_the_single_shot_path(tmp_path):
    """One attempt of the loop is the single-shot run."""
    client = _FakeClient()
    loop = _loop(tmp_path, client, max_attempts=1)
    single = run_agent(TASK_DIR, _FakeClient(), _settings(), STUB_PACK, tmp_path / "single")
    assert loop.run.status == single.status
    assert loop.run.error == single.error
    assert loop.run.prompt_version == single.prompt_version
    assert loop.run.input_tokens == single.input_tokens
    assert loop.run.output_tokens == single.output_tokens
    assert loop.run.cost_usd == single.cost_usd
    assert loop.run.attempts == single.attempts == 1
    assert len(client.requests) == 1


def test_one_attempt_reproduces_the_failed_single_shot_path(tmp_path):
    """One attempt of the loop is the single-shot run that failed."""
    loop = _loop(tmp_path, _FailingClient(), max_attempts=1)
    single = run_agent(TASK_DIR, _FailingClient(), _settings(), STUB_PACK, tmp_path / "single")
    assert loop.run.status == single.status == "error"
    assert loop.run.error == single.error
    assert loop.run.attempts == single.attempts == 1


def test_the_loop_leaves_the_committed_task_unchanged(tmp_path):
    """The loop writes into the scratch folder, never into the committed task."""
    before = _files(TASK_DIR)
    _loop(tmp_path, _FakeClient())
    assert _files(TASK_DIR) == before
    scratch = tmp_path.resolve() / TASK_ID / "project" / "parts"
    assert [path.name for path in scratch.iterdir()] == ["plt0001_candidate.stub"]
