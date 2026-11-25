"""Offline tests for expectation-free bounded generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.agent import generate as generate_module
from aturb.agent.config import agent_settings
from aturb.agent.generate import DEFAULT_PART_ID, generate_part
from aturb.agent.prompt import prompt_version
from aturb.agent.types import AgentError, ModelRequest, ModelResponse
from aturb.contract.types import BuildResult, FailureKind, PackInfo
from aturb.evals.judge import CandidateGeometry
from aturb.packs import load_manifest
from aturb.verify.step import load_step
from packs.stub.runner import StubRunner, fixture_bytes

REPO_ROOT = Path(__file__).resolve().parents[1]
STUB_PACK = load_manifest(REPO_ROOT / "packs" / "stub" / "pack.toml")
REQUIREMENT = "Build a rectangular plate with two holes."
GOOD = """# Units: millimetres
# --- PARAMS ---
LENGTH_MM = 120.0
WIDTH_MM = 60.0
# --- END PARAMS ---
"""
BAD = "# STUB: fail=syntax_error\n"


class _FakeClient:
    def __init__(self, answers: str | list[str] = GOOD, *, fail: bool = False):
        self.answers = [answers] if isinstance(answers, str) else answers
        self.fail = fail
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.fail:
            raise AgentError("canned provider failure")
        index = min(len(self.requests) - 1, len(self.answers) - 1)
        return ModelResponse(
            text=self.answers[index], input_tokens=100, output_tokens=50)


class _StaleRunner:
    """Write a stale STEP on attempt one and omit STEP on attempt two."""

    def __init__(self):
        self.clean_at_entry: list[bool] = []

    def info(self) -> PackInfo:
        return PackInfo(name="fake", language="stub-text", version="0.1")

    def build(self, request) -> BuildResult:
        project = Path(request.project_root)
        step = project / "out" / request.part_id / f"{request.part_id}.step"
        self.clean_at_entry.append(not step.exists())
        if len(self.clean_at_entry) == 2:
            return BuildResult(status="ok")
        step.parent.mkdir(parents=True, exist_ok=True)
        step.write_bytes(fixture_bytes())
        return BuildResult(
            status="failed", failure_kind=FailureKind.SYNTAX_ERROR,
            error_text="canned first-build failure")


class _CrashRunner:
    def info(self) -> PackInfo:
        return PackInfo(name="fake", language="stub-text", version="0.1")

    def build(self, request) -> BuildResult:
        raise RuntimeError("canned runner exception")


def _runner() -> StubRunner:
    return StubRunner(settings={}, pack_dir=STUB_PACK.pack_dir)


def _run(tmp_path: Path, client, *, runner=None, requirement=REQUIREMENT,
         part_id=DEFAULT_PART_ID, **overrides):
    settings = agent_settings({"agent": {
        "model": "fake-model", "input_price_per_mtok": 1.0,
        "output_price_per_mtok": 2.0,
    }})
    settings.update(overrides)
    return generate_part(
        requirement, tmp_path / "generated", client, runner or _runner(),
        settings, STUB_PACK, timeout_s=60, part_id=part_id)


def test_happy_path_builds_without_evaluation_fixtures(tmp_path):
    result = _run(tmp_path, _FakeClient())
    assert result.status == "ok"
    assert result.stop_reason == "built"
    assert result.attempts == 1
    assert result.geometry is not None
    assert result.geometry.is_valid and result.geometry.is_single_solid
    assert result.part_path is not None and result.part_path.is_file()
    assert result.step_path is not None and load_step(
        result.step_path).is_valid
    assert result.native_path is not None and result.native_path.is_file()
    assert result.conventions == ()
    names = {path.name for path in result.workspace.rglob("*")}
    assert not names & {"task.toml", "answer.toml", "expect"}


def test_build_failure_is_repaired_with_candidate_only_feedback(tmp_path):
    client = _FakeClient([BAD, GOOD])
    result = _run(tmp_path, client)
    assert result.status == "ok" and result.stop_reason == "built"
    assert result.attempts == 2
    repair = client.requests[1].prompt
    assert "## Repair" in repair
    assert "Previous candidate:" in repair
    assert BAD.strip() in repair
    assert result.input_tokens == 200 and result.output_tokens == 100
    assert result.cost_usd == pytest.approx(0.0004)
    assert result.prompt_version == prompt_version(client.requests[0].prompt)


def test_stale_step_is_removed_before_every_build_and_never_accepted(tmp_path):
    stale = (tmp_path / "generated" / "project" / "out" / DEFAULT_PART_ID
             / f"{DEFAULT_PART_ID}.step")
    stale.parent.mkdir(parents=True)
    stale.write_bytes(fixture_bytes())
    runner = _StaleRunner()
    result = _run(tmp_path, _FakeClient([BAD, GOOD]), runner=runner,
                  max_attempts=2)
    assert runner.clean_at_entry == [True, True]
    assert result.status == "error"
    assert result.stop_reason == "max_attempts"
    assert result.failure_kind == FailureKind.EXPORT_FAILED.value
    assert result.step_path is None and result.geometry is None
    assert result.error == "the build produced no STEP file"
    assert not stale.exists()


def test_invalid_geometry_is_retained_in_repair_feedback(tmp_path, monkeypatch):
    invalid = CandidateGeometry(
        is_valid=False, is_single_solid=True, volume=100.0,
        bbox_size=(10.0, 10.0, 1.0), holes=())
    original = generate_module.summarize_geometry
    summaries = iter((invalid, None))

    def summary(model):
        value = next(summaries)
        return value if value is not None else original(model)

    monkeypatch.setattr(generate_module, "summarize_geometry", summary)
    client = _FakeClient(GOOD)
    result = _run(tmp_path, client)
    repair = client.requests[1].prompt
    assert result.status == "ok" and result.attempts == 2
    assert "Build: ok" in repair
    assert "exported STEP is invalid or not a single solid" in repair
    assert "is_valid: false" in repair
    assert "Previous candidate:" in repair
    assert result.failure_kind == ""


def test_unreadable_step_maps_to_invalid_geometry(tmp_path, monkeypatch):
    monkeypatch.setattr("packs.stub.runner.fixture_bytes",
                        lambda: b"not a STEP")
    result = _run(tmp_path, _FakeClient(), max_attempts=1)
    assert result.stop_reason == "max_attempts"
    assert result.build_status == "failed"
    assert result.failure_kind == FailureKind.INVALID_GEOMETRY.value
    assert result.step_path is None and result.geometry is None
    assert "the STEP file could not be read" in result.error


def test_max_attempts_stops_a_repairable_failure(tmp_path):
    client = _FakeClient(BAD)
    result = _run(tmp_path, client, max_attempts=2)
    assert result.stop_reason == "max_attempts"
    assert result.attempts == len(client.requests) == 2
    assert result.failure_kind == FailureKind.SYNTAX_ERROR.value


def test_cumulative_budget_refuses_the_next_model_call(tmp_path):
    client = _FakeClient(BAD)
    result = _run(tmp_path, client, max_output_tokens=64,
                  max_total_output_tokens=64)
    assert result.stop_reason == "budget_exceeded"
    assert result.attempts == len(client.requests) == 1
    assert "cumulative output token budget" in result.error


@pytest.mark.parametrize("kind", ["runner_crash", "input_error"])
def test_unrepairable_failure_stops_after_one_build(tmp_path, kind):
    client = _FakeClient(f"# STUB: fail={kind}\n")
    result = _run(tmp_path, client)
    assert result.stop_reason == "unrepairable"
    assert result.failure_kind == kind
    assert result.attempts == len(client.requests) == 1


def test_unexpected_runner_exception_is_a_runner_crash(tmp_path):
    result = _run(tmp_path, _FakeClient(), runner=_CrashRunner())
    assert result.stop_reason == "unrepairable"
    assert result.failure_kind == FailureKind.RUNNER_CRASH.value
    assert "canned runner exception" in result.error


def test_model_error_stops_without_a_build(tmp_path):
    client = _FakeClient(fail=True)
    result = _run(tmp_path, client)
    assert result.stop_reason == "model_error"
    assert result.attempts == len(client.requests) == 1
    assert result.build_status == "" and result.part_path is None
    assert "the model call failed" in result.error


@pytest.mark.parametrize("kwargs", [
    {"requirement": "  "}, {"part_id": "../bad"}, {"max_attempts": 0},
])
def test_invalid_input_returns_a_clean_error(tmp_path, kwargs):
    client = _FakeClient()
    result = _run(tmp_path, client, **kwargs)
    assert result.status == "error" and result.stop_reason == "settings_error"
    assert result.attempts == 0 and client.requests == []


def test_one_attempt_does_not_start_a_repair(tmp_path):
    client = _FakeClient(BAD)
    result = _run(tmp_path, client, max_attempts=1)
    assert result.stop_reason == "max_attempts"
    assert result.attempts == len(client.requests) == 1
