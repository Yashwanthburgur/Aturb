"""End-to-end tests for the agent path, without a CAD and without a network.

The whole path is proven: the prompt is composed, the model answers with a
canned candidate, the stub pack builds it, the neutral checks run over the
exported STEP and the task is scored. The agent runs are recorded in their own
dated file, and the committed task folder is never written to.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aturb.agent.config import agent_settings
from aturb.agent.record import read_agent_runs
from aturb.agent.run import run_agent
from aturb.agent.types import AgentError, ModelRequest, ModelResponse
from aturb.cli import main
from aturb.packs import load_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"
STUB_PACK = load_manifest(REPO_ROOT / "packs" / "stub" / "pack.toml")

TASK_ID = "plate_2holes"
MODEL = "some-model-id"
CANDIDATE = "stub part file\n"
INPUT_TOKENS = 120
OUTPUT_TOKENS = 45
COST = (INPUT_TOKENS * 1.0 + OUTPUT_TOKENS * 2.0) / 1_000_000


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


def _files(folder: Path) -> set[str]:
    """Return the relative paths of every file under a folder."""
    return {
        path.relative_to(folder).as_posix()
        for path in folder.rglob("*")
        if path.is_file()
    }


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


def test_the_committed_task_folder_is_unchanged(tmp_path):
    """The run writes into the scratch area, never into the committed task."""
    before = _files(TASK_DIR)
    settings = agent_settings({"agent": {"model": MODEL}})

    run = run_agent(TASK_DIR, _FakeClient(), settings, STUB_PACK, tmp_path)

    assert run.status == "ok"
    assert _files(TASK_DIR) == before
    parts = TASK_DIR / "project" / "parts"
    assert list(parts.glob("*_candidate*")) == []


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
