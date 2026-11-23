"""End-to-end agent tests with canned clients, no CAD and no network."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from aturb.agent.attempts import attempts_path, read_attempts
from aturb.agent.config import agent_settings
from aturb.agent.conventions import check_conventions, conventions_text
from aturb.agent.loop import run_agent_loop
from aturb.agent.record import read_agent_runs
from aturb.agent.run import run_agent
from aturb.agent.types import AgentError, ModelRequest, ModelResponse
from aturb.cli import main
from aturb.packs import load_manifest, load_runner
from packs.stub.runner import fixture_bytes

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_SET = REPO_ROOT / "evals" / "tasks"
TASK_DIR = TASK_SET / "plate_2holes"
FILLET_TASK_DIR = TASK_SET / "plate_fillet"
STUB_PACK = load_manifest(REPO_ROOT / "packs" / "stub" / "pack.toml")
TASK_ID = "plate_2holes"
PART_ID = "plt0001"
FILLET_PART_ID = "plt0002"
MODEL = "some-model-id"
CANDIDATE = """\
# PLT0001 Base plate. Units: millimetres.
# The stub pack ignores the content of this file.
# --- PARAMS ---
LENGTH_MM = 120.0
WIDTH_MM = 60.0
THICKNESS_MM = 5.0
# --- END PARAMS ---
"""
WRONG = "# a wrong first candidate\n"
INPUT_TOKENS = 120
OUTPUT_TOKENS = 45
COST = (INPUT_TOKENS * 1.0 + OUTPUT_TOKENS * 2.0) / 1_000_000
PROBE_TIMEOUT_S = 60  # starting default
CORE_PROBE = (
    "import sys\n"
    "import aturb.agent.run\n"
    "leaked = [name for name in sys.modules\n"
    "          if name.split('.')[0] in ('packs', 'freecad', 'FreeCAD')]\n"
    "assert not leaked, leaked\n"
    "assert not hasattr(aturb.agent.run, 'helper')\n"
    "print('CORE_ISOLATED')\n"
)


class _FakeClient:
    def __init__(self, text: str | list[str] = CANDIDATE) -> None:
        self.answers = [text] if isinstance(text, str) else text
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.answers) - 1)
        return ModelResponse(text=self.answers[index], input_tokens=INPUT_TOKENS,
                             output_tokens=OUTPUT_TOKENS)


class _FlakyClient:
    def __init__(self, failures: int = 1) -> None:
        self.failures = failures
        self.calls = 0

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.calls <= self.failures:
            raise AgentError("the provider refused the call")
        return ModelResponse(text=CANDIDATE, input_tokens=INPUT_TOKENS,
                             output_tokens=OUTPUT_TOKENS)


def _write_config(tmp_path: Path) -> Path:
    config = tmp_path / "aturb.local.toml"
    config.write_text(
        'active_pack = "stub"\n[packs.stub]\n[timeouts]\nbuild_s = 60\n'
        f'[agent]\nmodel = "{MODEL}"\ninput_price_per_mtok = 1.0\n'
        "output_price_per_mtok = 2.0\n", encoding="utf-8")
    return config


def _make_task_set(tmp_path: Path, count: int = 1) -> Path:
    tasks = tmp_path / "tasks"
    tasks.mkdir(exist_ok=True)
    for index in range(1, count + 1):
        name = TASK_ID if index == 1 else f"{TASK_ID}_{index}"
        shutil.copytree(TASK_DIR, tasks / name,
                        ignore=shutil.ignore_patterns("out"))
        if index > 1:
            _rename_task(tasks / name, name)
    return tasks


def _rename_task(task_dir: Path, task_id: str) -> None:
    for name in ("task.toml", "answer.toml"):
        path = task_dir / name
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(f'task_id = "{TASK_ID}"',
                                     f'task_id = "{task_id}"'), encoding="utf-8")


def _snapshot(folder: Path) -> dict[str, bytes]:
    return {path.relative_to(folder).as_posix(): path.read_bytes()
            for path in sorted(folder.rglob("*")) if path.is_file()}


def _expected_values(task_dir: Path, part_id: str) -> dict:
    path = task_dir / "project" / "expect" / f"{part_id}.toml"
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _agent_file(results_dir: Path) -> Path:
    files = list(results_dir.glob("*_agent.toml"))
    assert len(files) == 1
    return files[0]


def _eval(tasks: Path, tmp_path: Path, results: Path) -> int:
    return main(["eval", str(tasks), "--agent", "--config",
                 str(_write_config(tmp_path)), "--results-dir", str(results)])


def _loop(task: Path, client, tmp_path: Path, **overrides):
    settings = agent_settings({"agent": {"model": MODEL, **overrides}})
    runner = load_runner("stub", {"packs": {}}, REPO_ROOT / "packs")
    return run_agent_loop(task, client, runner, settings, STUB_PACK, tmp_path, 60)


def _wrong_step(tmp_path: Path) -> bytes:
    from build123d import Box, export_step
    path = tmp_path / "wrong.step"
    export_step(Box(10, 10, 10), str(path))
    return path.read_bytes()


def _scripted_steps(tmp_path: Path, monkeypatch) -> None:
    payloads = iter((_wrong_step(tmp_path), fixture_bytes()))
    monkeypatch.setattr("packs.stub.runner.fixture_bytes",
                        lambda: next(payloads))


def test_the_agent_path_scores_the_task(tmp_path, capsys, monkeypatch):
    tasks, results, client = _make_task_set(
        tmp_path), tmp_path / "results", _FakeClient()
    monkeypatch.setattr("aturb.cli._model_client", lambda settings: client)
    code = _eval(tasks, tmp_path, results)
    out = capsys.readouterr().out
    assert code == 0
    assert "task plate_2holes ok score=1.0" in out
    assert len(client.requests) == 1
    step = (tmp_path / "tmp" / "agent" / TASK_ID / "project" / "out"
            / "plt0001" / "plt0001.step")
    assert step.is_file()


def test_the_agent_run_file_holds_one_record_per_task(tmp_path, capsys, monkeypatch):
    tasks, results = _make_task_set(tmp_path), tmp_path / "results"
    monkeypatch.setattr("aturb.cli._model_client",
                        lambda settings: _FakeClient())
    code = _eval(tasks, tmp_path, results)
    capsys.readouterr()
    assert code == 0
    runs = read_agent_runs(_agent_file(results))
    assert len(runs) == 1
    run = runs[0]
    assert run.task_id == TASK_ID
    assert run.model == MODEL
    assert len(run.prompt_version) == 16
    assert run.input_tokens == INPUT_TOKENS
    assert run.output_tokens == OUTPUT_TOKENS
    assert run.cost_usd == pytest.approx(COST)


def test_the_prompt_of_the_run_carries_the_conventions_and_no_expected_value(tmp_path):
    settings = agent_settings({"agent": {"model": MODEL}})
    for task_dir, part_id in ((TASK_DIR, PART_ID), (FILLET_TASK_DIR, FILLET_PART_ID)):
        client = _FakeClient()
        run = run_agent(task_dir, client, settings, STUB_PACK, tmp_path)
        assert run.status == "ok"
        prompt = client.requests[0].prompt
        assert conventions_text().strip() in prompt
        expected = _expected_values(task_dir, part_id)
        assert str(expected["volume"]) not in prompt


def test_the_candidate_of_the_run_follows_the_conventions(tmp_path):
    client = _FakeClient()
    settings = agent_settings({"agent": {"model": MODEL}})
    run = run_agent(TASK_DIR, client, settings, STUB_PACK, tmp_path)
    assert run.status == "ok"
    candidate = (tmp_path / TASK_ID / "project" / "parts"
                 / f"{PART_ID}_candidate{STUB_PACK.part_extension}")
    assert candidate.is_file()
    text = candidate.read_text(encoding="utf-8")
    assert check_conventions(PART_ID, STUB_PACK.part_extension, text) == []


def test_the_committed_task_set_is_unchanged_after_the_run(tmp_path):
    before = _snapshot(TASK_SET)
    settings = agent_settings({"agent": {"model": MODEL}})
    folders = [path for path in sorted(TASK_SET.iterdir()) if path.is_dir()]
    for folder in folders:
        run = run_agent(folder, _FakeClient(), settings, STUB_PACK, tmp_path)
        assert run.status == "ok"
    assert _snapshot(TASK_SET) == before
    for folder in folders:
        parts = folder / "project" / "parts"
        assert list(parts.glob("*_candidate*")) == []


def test_the_helper_is_not_reachable_from_the_core():
    proc = subprocess.run([sys.executable, "-c", CORE_PROBE], cwd=REPO_ROOT,
                          capture_output=True, text=True, timeout=PROBE_TIMEOUT_S)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CORE_ISOLATED" in proc.stdout


def test_a_failing_client_gives_an_error_run_and_the_run_goes_on(tmp_path, capsys, monkeypatch):
    tasks, results = _make_task_set(tmp_path, count=2), tmp_path / "results"
    client = _FlakyClient(failures=1)
    monkeypatch.setattr("aturb.cli._model_client", lambda settings: client)
    code = _eval(tasks, tmp_path, results)
    out = capsys.readouterr().out
    assert code == 1
    assert "task plate_2holes error score=0.0" in out
    assert "task plate_2holes_2 ok score=1.0" in out
    runs = read_agent_runs(_agent_file(results))
    assert [(run.task_id, run.status) for run in runs] == [
        (TASK_ID, "error"), (f"{TASK_ID}_2", "ok")]


def test_the_cli_repairs_wrong_geometry_and_records_both_attempts(
        tmp_path, capsys, monkeypatch):
    tasks, results = _make_task_set(tmp_path), tmp_path / "results"
    client = _FakeClient([WRONG, CANDIDATE])
    _scripted_steps(tmp_path, monkeypatch)
    monkeypatch.setattr("aturb.cli._model_client", lambda settings: client)
    code = _eval(tasks, tmp_path, results)
    out = capsys.readouterr().out
    assert code == 0
    assert "task plate_2holes ok score=1.0" in out
    assert len(client.requests) == 2
    assert read_agent_runs(_agent_file(results))[0].attempts == 2
    attempts = read_attempts(attempts_path(_agent_file(results)))
    assert [item.attempt for item in attempts] == [1, 2]
    assert [item.score for item in attempts] == [0.0, 1.0]


@pytest.mark.parametrize("task_dir,part_id", [
    (TASK_DIR, PART_ID), (FILLET_TASK_DIR, FILLET_PART_ID)])
def test_repair_prompt_has_candidate_geometry_and_no_evaluator_fields(
        tmp_path, monkeypatch, task_dir, part_id):
    client = _FakeClient([WRONG, CANDIDATE])
    _scripted_steps(tmp_path, monkeypatch)
    loop = _loop(task_dir, client, tmp_path, max_attempts=2)
    repair = client.requests[1].prompt
    assert loop.run.attempts == 2
    for text in ("Candidate geometry (measured from the exported STEP):",
                 "is_valid: true", "is_single_solid: true", "volume: 1000.0 mm^3",
                 "bbox_size: 10.0 x 10.0 x 10.0 mm", "holes: 0"):
        assert text in repair
    expected = _expected_values(task_dir, part_id)
    forbidden = (str(expected["volume"]), "volume =", "tolerance", "bbox_x", "bbox_y",
                 "bbox_z", "hole_count", "required_checks", "max_score", "score=",
                 "verdict", "passed", "the checks did not pass", f"expect/{part_id}.toml",
                 loop.attempts[0].error)
    for text in forbidden:
        assert text not in repair


def test_the_loop_stops_at_limits_budgets_and_unrepairable_failures(tmp_path):
    client = _FakeClient(["# STUB: fail=syntax_error\n"])
    loop = _loop(TASK_DIR, client, tmp_path / "attempts", max_attempts=2)
    assert loop.stop_reason == "max_attempts"
    assert len(client.requests) == loop.run.attempts == 2
    for kind in ("runner_crash", "input_error"):
        client = _FakeClient([f"# STUB: fail={kind}\n"])
        loop = _loop(TASK_DIR, client, tmp_path / kind)
        assert loop.stop_reason == "unrepairable"
        assert len(client.requests) == 1
    client = _FakeClient(["# STUB: fail=syntax_error\n"])
    loop = _loop(TASK_DIR, client, tmp_path / "budget", max_output_tokens=512,
                 max_total_output_tokens=512)
    assert loop.stop_reason == "budget_exceeded"
    assert len(client.requests) == 1
    assert "budget" in loop.attempts[-1].error
