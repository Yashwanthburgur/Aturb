"""End-to-end tests for the agent path, without a CAD and without a network.

The whole path is proven: the prompt is composed, the model answers with a
canned candidate, the stub pack builds it, the neutral checks run over the
exported STEP and the task is scored. The committed task set is never written to.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from aturb.agent.config import agent_settings
from aturb.agent.conventions import check_conventions, conventions_text
from aturb.agent.record import read_agent_runs
from aturb.agent.run import run_agent
from aturb.agent.types import AgentError, ModelRequest, ModelResponse
from aturb.cli import main
from aturb.packs import load_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_SET = REPO_ROOT / "evals" / "tasks"
TASK_DIR = TASK_SET / "plate_2holes"
FILLET_TASK_DIR = TASK_SET / "plate_fillet"
STUB_PACK = load_manifest(REPO_ROOT / "packs" / "stub" / "pack.toml")

TASK_ID = "plate_2holes"
PART_ID = "plt0001"
FILLET_PART_ID = "plt0002"
MODEL = "some-model-id"
# The canned answer of the fake client: a stub part file that follows the
# project conventions, so the run proves that a candidate can meet them.
CANDIDATE = """\
# PLT0001 Base plate. Units: millimetres.
# The stub pack ignores the content of this file.
# --- PARAMS ---
LENGTH_MM = 120.0
WIDTH_MM = 60.0
THICKNESS_MM = 5.0
# --- END PARAMS ---
"""
INPUT_TOKENS = 120
OUTPUT_TOKENS = 45
COST = (INPUT_TOKENS * 1.0 + OUTPUT_TOKENS * 2.0) / 1_000_000
PROBE_TIMEOUT_S = 60  # starting default

# The probe runs in a fresh interpreter, so the import graph of the core is
# seen as it is and not as the test session left it.
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
    """A model client that answers with a canned candidate."""

    def __init__(self, text: str = CANDIDATE) -> None:
        """Take the candidate the client returns."""
        self.text = text
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Record the request and return the canned candidate."""
        self.requests.append(request)
        return ModelResponse(
            text=self.text,
            input_tokens=INPUT_TOKENS,
            output_tokens=OUTPUT_TOKENS,
        )


class _FlakyClient:
    """A model client whose first calls fail and whose next ones answer."""

    def __init__(self, failures: int = 1) -> None:
        """Take the number of calls that fail."""
        self.failures = failures
        self.calls = 0

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Fail the first calls and answer the next ones."""
        self.calls += 1
        if self.calls <= self.failures:
            raise AgentError("the provider refused the call")
        return ModelResponse(
            text=CANDIDATE,
            input_tokens=INPUT_TOKENS,
            output_tokens=OUTPUT_TOKENS,
        )


def _write_config(tmp_path: Path) -> Path:
    """Write a tmp config with the stub pack and the agent settings."""
    config = tmp_path / "aturb.local.toml"
    config.write_text(
        'active_pack = "stub"\n'
        "[packs.stub]\n"
        "[timeouts]\nbuild_s = 60\n"
        "[agent]\n"
        f'model = "{MODEL}"\n'
        "input_price_per_mtok = 1.0\n"
        "output_price_per_mtok = 2.0\n",
        encoding="utf-8",
    )
    return config


def _make_task_set(tmp_path: Path, count: int = 1) -> Path:
    """Copy the committed task set into tmp_path and return the set folder.

    Every task after the first one gets a task ID of its own, so the set holds
    several tasks that the agent runs one after the other.
    """
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
    """Give a copied task folder a task ID of its own."""
    for name in ("task.toml", "answer.toml"):
        path = task_dir / name
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(f'task_id = "{TASK_ID}"', f'task_id = "{task_id}"'),
            encoding="utf-8",
        )


def _snapshot(folder: Path) -> dict[str, bytes]:
    """Return the path and the bytes of every file under a folder.

    The bytes are read, so a file changed in place is seen as changed.
    """
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def _expected_values(task_dir: Path, part_id: str) -> dict:
    """Return the expected values of a part, read from its expectation file."""
    path = task_dir / "project" / "expect" / f"{part_id}.toml"
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _agent_file(results_dir: Path) -> Path:
    """Return the agent run file of a run."""
    files = list(results_dir.glob("*_agent.toml"))
    assert len(files) == 1
    return files[0]


def test_the_agent_path_scores_the_task(tmp_path, capsys, monkeypatch):
    """The agent writes a candidate, the stub pack builds it and the task scores 1.0."""
    tasks = _make_task_set(tmp_path)
    results = tmp_path / "results"
    client = _FakeClient()
    monkeypatch.setattr("aturb.cli._model_client", lambda settings: client)

    code = main(["eval", str(tasks), "--agent",
                 "--config", str(_write_config(tmp_path)),
                 "--results-dir", str(results)])

    out = capsys.readouterr().out
    assert code == 0
    assert "task plate_2holes ok score=1.0" in out
    assert len(client.requests) == 1
    step = (tmp_path / "tmp" / "agent" / TASK_ID / "project" / "out"
            / "plt0001" / "plt0001.step")
    assert step.is_file()


def test_the_agent_run_file_holds_one_record_per_task(tmp_path, capsys, monkeypatch):
    """The agent run file holds the model, the prompt version, the tokens and the cost."""
    tasks = _make_task_set(tmp_path)
    results = tmp_path / "results"
    monkeypatch.setattr("aturb.cli._model_client",
                        lambda settings: _FakeClient())

    code = main(["eval", str(tasks), "--agent",
                 "--config", str(_write_config(tmp_path)),
                 "--results-dir", str(results)])

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
    """The prompt carries the conventions and no expected value of the task."""
    settings = agent_settings({"agent": {"model": MODEL}})
    for task_dir, part_id in ((TASK_DIR, PART_ID),
                              (FILLET_TASK_DIR, FILLET_PART_ID)):
        client = _FakeClient()
        run = run_agent(task_dir, client, settings, STUB_PACK, tmp_path)

        assert run.status == "ok"
        prompt = client.requests[0].prompt
        assert conventions_text().strip() in prompt
        # ADR-0008: the expected values of the evaluator never reach the model.
        expected = _expected_values(task_dir, part_id)
        assert str(expected["volume"]) not in prompt


def test_the_candidate_of_the_run_follows_the_conventions(tmp_path):
    """The candidate the agent writes follows the conventions of the project."""
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
    """The run writes into the scratch area, never into the committed tasks."""
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
    """The core never imports the pack, so the helper stays in the pack."""
    proc = subprocess.run([sys.executable, "-c", CORE_PROBE], cwd=REPO_ROOT,
                          capture_output=True, text=True, timeout=PROBE_TIMEOUT_S)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CORE_ISOLATED" in proc.stdout


def test_a_failing_client_gives_an_error_run_and_the_run_goes_on(tmp_path, capsys, monkeypatch):
    """A client that fails gives an error run and an error result, and the next task runs."""
    tasks = _make_task_set(tmp_path, count=2)
    results = tmp_path / "results"
    client = _FlakyClient(failures=1)
    monkeypatch.setattr("aturb.cli._model_client", lambda settings: client)

    code = main(["eval", str(tasks), "--agent",
                 "--config", str(_write_config(tmp_path)),
                 "--results-dir", str(results)])

    out = capsys.readouterr().out
    assert code == 1
    assert "task plate_2holes error score=0.0" in out
    assert "task plate_2holes_2 ok score=1.0" in out
    runs = read_agent_runs(_agent_file(results))
    assert [(run.task_id, run.status) for run in runs] == [
        (TASK_ID, "error"), (f"{TASK_ID}_2", "ok")]
