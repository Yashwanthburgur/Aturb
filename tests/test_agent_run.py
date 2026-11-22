"""Tests for one agent run, with a fake client and no network."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aturb.agent.config import agent_settings
from aturb.agent.prompt import prompt_version
from aturb.agent.run import prepare_run, run_agent, run_attempt
from aturb.agent.types import AgentError, ModelRequest, ModelResponse
from aturb.evals.runner import run_task
from aturb.packs import PackManifest, load_manifest, load_runner

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"
PACKS_ROOT = REPO_ROOT / "packs"
STUB_PACK = load_manifest(PACKS_ROOT / "stub" / "pack.toml")
TASK_ID = "plate_2holes"
PART_ID = "plt0001"
CANDIDATE = "# the candidate part\n"
EXPECT_FILE = TASK_DIR / "project" / "expect" / f"{PART_ID}.toml"
SENTINEL = "35214.602"


class _FakeClient:
    """A client that records the request and returns a canned answer."""

    def __init__(self, text: str = CANDIDATE, input_tokens: int = 120,
                 output_tokens: int = 45) -> None:
        """Take the answer the client returns."""
        self.text, self.input_tokens = text, input_tokens
        self.output_tokens = output_tokens
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Record the request and return the canned answer."""
        self.requests.append(request)
        return ModelResponse(text=self.text, input_tokens=self.input_tokens,
                             output_tokens=self.output_tokens)


class _FailingClient:
    """A client whose call always fails."""

    def __init__(self, failure: Exception | None = None) -> None:
        """Take the failure the client raises."""
        self.failure = failure or AgentError("the provider refused the call")
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Record the request and fail."""
        self.requests.append(request)
        raise self.failure


def _settings(**overrides) -> dict:
    """Return the agent settings of the tests."""
    return {**agent_settings({}), **overrides}


def _candidate(work_dir: Path) -> Path:
    """Return the path of the candidate of the committed task."""
    parts = Path(work_dir).resolve() / TASK_ID / "project" / "parts"
    return parts / f"{PART_ID}_candidate.stub"


def _files(folder: Path) -> set[str]:
    """Return the relative paths of every file under a folder."""
    return {path.relative_to(folder).as_posix()
            for path in folder.rglob("*") if path.is_file()}


def _task_without_requirements(tmp_path: Path) -> Path:
    """Return a copy of the committed task without its requirement file."""
    task = tmp_path / TASK_ID
    shutil.copytree(TASK_DIR, task)
    shutil.rmtree(task / "project" / "requirements")
    return task


def test_a_good_run_writes_the_candidate(tmp_path):
    """A good run writes the candidate into the scratch project."""
    run = run_agent(TASK_DIR, _FakeClient(), _settings(), STUB_PACK, tmp_path)
    assert run.status == "ok"
    assert run.error == ""
    assert _candidate(tmp_path).read_text(encoding="utf-8") == CANDIDATE


def test_a_good_run_reports_the_tokens_of_the_provider(tmp_path):
    """The token counts of the run are the ones the provider reported."""
    client = _FakeClient(input_tokens=120, output_tokens=45)
    run = run_agent(TASK_DIR, client, _settings(), STUB_PACK, tmp_path)
    assert run.input_tokens == 120
    assert run.output_tokens == 45


def test_the_prompt_version_is_the_hash_of_the_prompt(tmp_path):
    """The prompt version is the hash of the exact text sent to the model."""
    client = _FakeClient()
    run = run_agent(TASK_DIR, client, _settings(), STUB_PACK, tmp_path)
    assert run.prompt_version == prompt_version(client.requests[0].prompt)


def test_the_prompt_holds_the_requirement(tmp_path):
    """The prompt holds the requirement of the task."""
    client = _FakeClient()
    run_agent(TASK_DIR, client, _settings(), STUB_PACK, tmp_path)
    prompt = client.requests[0].prompt
    assert "120 mm long in X" in prompt


def test_the_prompt_holds_no_expected_value(tmp_path):
    """No value of the expectation file reaches the prompt (ADR-0008)."""
    client = _FakeClient()
    run_agent(TASK_DIR, client, _settings(), STUB_PACK, tmp_path)
    prompt = client.requests[0].prompt
    for line in EXPECT_FILE.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            assert line not in prompt
    assert SENTINEL not in prompt


def test_the_evaluator_still_scores_the_candidate(tmp_path):
    """The scratch folder keeps the expectation file and the evaluator scores."""
    client = _FakeClient()
    run_agent(TASK_DIR, client, _settings(), STUB_PACK, tmp_path)
    scratch = tmp_path.resolve() / TASK_ID
    assert (scratch / "project" / "expect" / f"{PART_ID}.toml").is_file()
    runner = load_runner("stub", {"packs": {}}, PACKS_ROOT)
    result = run_task(scratch, runner, timeout_s=60)
    assert result.status == "ok"
    assert result.score == 1.0


def test_the_cost_is_zero_without_a_configured_price(tmp_path):
    """Without a configured price the cost of the run is zero."""
    run = run_agent(TASK_DIR, _FakeClient(), _settings(), STUB_PACK, tmp_path)
    assert run.cost_usd == 0.0


def test_the_cost_comes_from_the_configured_prices(tmp_path):
    """The cost of the run is computed from the reported usage."""
    settings = _settings(input_price_per_mtok=1.0, output_price_per_mtok=2.0)
    client = _FakeClient(input_tokens=1000, output_tokens=500)
    run = run_agent(TASK_DIR, client, settings, STUB_PACK, tmp_path)
    assert run.cost_usd == pytest.approx(0.002)


def test_a_call_that_would_pass_the_budget_is_refused(tmp_path):
    """A call that would pass the budget is refused without calling the model."""
    settings = _settings(input_price_per_mtok=1000.0, output_price_per_mtok=1000.0,
                         max_cost_usd=0.001)
    client = _FakeClient()
    run = run_agent(TASK_DIR, client, settings, STUB_PACK, tmp_path)
    assert run.status == "error"
    assert "budget" in run.error
    assert client.requests == []


def test_a_prompt_over_the_input_cap_is_refused(tmp_path):
    """A prompt over the input token cap is refused without calling the model."""
    client = _FakeClient()
    run = run_agent(TASK_DIR, client, _settings(
        max_input_tokens=1), STUB_PACK, tmp_path)
    assert run.status == "error"
    assert "token" in run.error
    assert client.requests == []


def test_a_failed_call_is_an_error_run(tmp_path):
    """A call that fails is an error run, never an exception."""
    client = _FailingClient()
    run = run_agent(TASK_DIR, client, _settings(), STUB_PACK, tmp_path)
    assert run.status == "error"
    assert "the model call failed" in run.error
    assert run.attempts == 1


def test_an_empty_answer_is_an_error_run(tmp_path):
    """An empty answer is an error run and no candidate is written."""
    client = _FakeClient(text="")
    run = run_agent(TASK_DIR, client, _settings(), STUB_PACK, tmp_path)
    assert run.status == "error"
    assert "empty" in run.error
    assert not _candidate(tmp_path).exists()


def test_a_missing_requirement_file_is_an_error_run(tmp_path):
    """A task without a requirement file is an error run."""
    task = _task_without_requirements(tmp_path)
    run = run_agent(task, _FakeClient(), _settings(),
                    STUB_PACK, tmp_path / "work")
    assert run.status == "error"
    assert "requirement" in run.error


def test_a_missing_pack_prompt_is_an_error_run(tmp_path):
    """A pack without a prompt file is an error run."""
    pack = PackManifest(
        name=STUB_PACK.name, language=STUB_PACK.language,
        part_extension=STUB_PACK.part_extension, runner=STUB_PACK.runner,
        prompt_dir="no_prompt", contract_version=STUB_PACK.contract_version,
        pack_dir=STUB_PACK.pack_dir)
    run = run_agent(TASK_DIR, _FakeClient(), _settings(), pack, tmp_path)
    assert run.status == "error"
    assert "pack prompt" in run.error


def test_the_client_is_called_exactly_once(tmp_path):
    """One run is one call of the model."""
    client = _FakeClient()
    run_agent(TASK_DIR, client, _settings(), STUB_PACK, tmp_path)
    assert len(client.requests) == 1


def test_the_request_carries_the_model_and_the_output_cap(tmp_path):
    """The request holds the configured model and the output cap."""
    client = _FakeClient()
    settings = _settings(model="some-model-id", max_output_tokens=512)
    run_agent(TASK_DIR, client, settings, STUB_PACK, tmp_path)
    assert client.requests[0].model == "some-model-id"
    assert client.requests[0].max_output_tokens == 512


def test_the_run_records_the_provider_and_the_model(tmp_path):
    """The run records the provider and the model of the configuration."""
    settings = _settings(provider="some-provider", model="some-model-id")
    run = run_agent(TASK_DIR, _FakeClient(), settings, STUB_PACK, tmp_path)
    assert run.provider == "some-provider"
    assert run.model == "some-model-id"


def test_the_code_fence_of_the_answer_is_stripped(tmp_path):
    """One code fence around the answer is stripped."""
    client = _FakeClient(text="```python\n# the candidate part\n```")
    run_agent(TASK_DIR, client, _settings(), STUB_PACK, tmp_path)
    assert _candidate(tmp_path).read_text(encoding="utf-8") == CANDIDATE


def test_the_scratch_folder_holds_no_reference_part(tmp_path):
    """The scratch folder holds the candidate and no reference part."""
    run_agent(TASK_DIR, _FakeClient(), _settings(), STUB_PACK, tmp_path)
    parts = tmp_path.resolve() / TASK_ID / "project" / "parts"
    assert [path.name for path in parts.iterdir()] == [
        f"{PART_ID}_candidate.stub"]


def test_the_committed_task_is_unchanged(tmp_path):
    """The run leaves the committed task exactly as it was."""
    before = _files(TASK_DIR)
    run_agent(TASK_DIR, _FakeClient(), _settings(), STUB_PACK, tmp_path)
    assert _files(TASK_DIR) == before


def test_every_run_has_one_attempt(tmp_path):
    """Every run of this phase has one attempt."""
    good = run_agent(TASK_DIR, _FakeClient(), _settings(), STUB_PACK, tmp_path)
    bad = run_agent(TASK_DIR, _FailingClient(),
                    _settings(), STUB_PACK, tmp_path)
    assert good.attempts == 1
    assert bad.attempts == 1


def test_an_attempt_puts_the_feedback_in_the_prompt(tmp_path):
    """The feedback of the attempt is in the prompt of the model."""
    prepared = prepare_run(TASK_DIR, STUB_PACK, tmp_path)
    client = _FakeClient()
    run_attempt(prepared, client, _settings(), STUB_PACK, "## Repair\nfix it")
    assert "## Repair" in client.requests[0].prompt


def test_an_attempt_reports_the_version_the_tokens_and_the_cost(tmp_path):
    """The outcome of the attempt holds the version, the tokens and the cost."""
    prepared = prepare_run(TASK_DIR, STUB_PACK, tmp_path)
    client = _FakeClient(input_tokens=1000, output_tokens=500)
    settings = _settings(input_price_per_mtok=1.0, output_price_per_mtok=2.0)
    outcome = run_attempt(prepared, client, settings, STUB_PACK)
    assert outcome.status == "ok"
    assert outcome.prompt_version == prompt_version(client.requests[0].prompt)
    assert (outcome.input_tokens, outcome.output_tokens) == (1000, 500)
    assert outcome.cost_usd == pytest.approx(0.002)


def test_a_second_attempt_replaces_the_candidate(tmp_path):
    """A second attempt over the same scratch replaces the candidate."""
    prepared = prepare_run(TASK_DIR, STUB_PACK, tmp_path)
    run_attempt(prepared, _FakeClient(), _settings(), STUB_PACK)
    outcome = run_attempt(prepared, _FakeClient(text="# the second part\n"),
                          _settings(), STUB_PACK)
    assert outcome.candidate_text == "# the second part\n"
    assert outcome.candidate_path == _candidate(tmp_path)
    assert _candidate(tmp_path).read_text(
        encoding="utf-8") == "# the second part\n"
