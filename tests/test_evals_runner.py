"""Tests for the task runner.

One task folder is built through the runner contract and judged against the
answer of the task. Every failure is a result: a task that cannot be judged
is an error result, and a task whose checks did not pass is a failed result.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from aturb.contract.types import BuildRequest, BuildResult, PackInfo
from aturb.evals.result import ERROR, FAILED, OK
from aturb.evals.runner import run_task
from aturb.packs import default_packs_root, load_runner

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"

EXPECT_FILE = """\
volume = 35214.602
bbox = [120.0, 60.0, 5.0]
hole_count = 2
hole_diameter = 10.0
hole_positions = [[-40.0, 0.0], [40.0, 0.0]]
"""

WRONG_VOLUME = EXPECT_FILE.replace("volume = 35214.602", "volume = 999.0")


def make_runner():
    """Load the stub runner with empty settings."""
    return load_runner("stub", {"packs": {}}, default_packs_root())


def copy_task(tmp_path: Path) -> Path:
    """Copy the committed task into a tmp folder and return it."""
    folder = tmp_path / "plate_2holes"
    shutil.copytree(TASK_DIR, folder, ignore=shutil.ignore_patterns("out"))
    return folder


class SpyRunner:
    """A runner that remembers the request it was given."""

    def __init__(self, inner):
        self.inner = inner
        self.requests: list[BuildRequest] = []

    def info(self) -> PackInfo:
        """Describe the pack."""
        return self.inner.info()

    def build(self, request: BuildRequest) -> BuildResult:
        """Build one part and remember the request."""
        self.requests.append(request)
        return self.inner.build(request)


class FakeRunner:
    """A runner that reports a build with a chosen STEP artifact."""

    def __init__(self, step: str | None = None):
        self.step = step

    def info(self) -> PackInfo:
        """Describe the pack."""
        return PackInfo(name="stub", language="stub-text", version="0.1")

    def build(self, request: BuildRequest) -> BuildResult:
        """Report a build that produced the chosen STEP artifact."""
        artifacts = {} if self.step is None else {"step": self.step}
        return BuildResult(status="ok", artifacts=artifacts)


def test_the_committed_task_builds_and_scores_one():
    """The committed task builds through the stub pack and scores 1.0."""
    result = run_task(TASK_DIR, make_runner(), 60)

    assert result.status == OK
    assert result.score == 1.0
    assert result.task_id == "plate_2holes"
    assert result.part_id == "plt0001"
    assert result.error == ""


def test_the_request_carries_the_part_id_and_the_project():
    """The request names the part of the task and its own project."""
    spy = SpyRunner(make_runner())

    run_task(TASK_DIR, spy, 60)

    request = spy.requests[0]
    assert request.part_id == "plt0001"
    assert request.project_root.replace(
        "\\", "/").endswith("plate_2holes/project")
    assert request.language == "stub-text"
    assert request.outputs == ("native", "step")
    assert request.timeout_s == 60


def test_the_answer_file_stays_out_of_the_build_project():
    """The runner is never given the answer of the task."""
    spy = SpyRunner(make_runner())

    run_task(TASK_DIR, spy, 60)

    project = Path(spy.requests[0].project_root)
    assert project == (TASK_DIR / "project").resolve()
    assert not (project / "answer.toml").exists()


def test_a_task_without_a_task_file_is_an_error(tmp_path):
    """A task folder without a task file is an error named after the folder."""
    folder = tmp_path / "plate_2holes"
    folder.mkdir()

    result = run_task(folder, make_runner(), 60)

    assert result.status == ERROR
    assert result.task_id == "plate_2holes"
    assert result.part_id == ""
    assert result.score == 0.0
    assert result.error


def test_a_task_with_an_unreadable_answer_is_an_error(tmp_path):
    """An answer file that cannot be read is an error of the task."""
    folder = copy_task(tmp_path)
    answer = folder / "answer.toml"
    answer.write_text(
        answer.read_text(encoding="utf-8") + 'prompt = "Build the plate."\n',
        encoding="utf-8")

    result = run_task(folder, make_runner(), 60)

    assert result.status == ERROR
    assert result.task_id == "plate_2holes"
    assert result.part_id == "plt0001"
    assert result.error


def test_a_task_without_a_project_folder_is_an_error(tmp_path):
    """A task folder without a project folder is an error."""
    folder = copy_task(tmp_path)
    shutil.rmtree(folder / "project")

    result = run_task(folder, make_runner(), 60)

    assert result.status == ERROR
    assert result.task_id == "plate_2holes"
    assert result.error


def test_a_failed_build_is_an_error(tmp_path):
    """A build that fails is an error that keeps the text of the failure."""
    folder = copy_task(tmp_path)
    (folder / "project" / "parts" / "plt0001_base_plate.stub").write_text(
        "# STUB: fail=runtime_error\n", encoding="utf-8")

    result = run_task(folder, make_runner(), 60)

    assert result.status == ERROR
    assert result.score == 0.0
    assert "scripted failure" in result.error


def test_a_build_without_a_step_file_is_an_error():
    """A build that produced no STEP file is an error."""
    result = run_task(TASK_DIR, FakeRunner(), 60)

    assert result.status == ERROR
    assert result.task_id == "plate_2holes"
    assert "no STEP file" in result.error


def test_a_step_file_that_cannot_be_read_is_an_error():
    """A STEP file that is not there is an error."""
    result = run_task(TASK_DIR, FakeRunner("out/plt0001/gone.step"), 60)

    assert result.status == ERROR
    assert "STEP file" in result.error


def test_a_task_whose_checks_fail_is_failed(tmp_path):
    """A task whose checks did not pass is failed and says which check failed."""
    folder = copy_task(tmp_path)
    (folder / "project" / "expect" / "plt0001.toml").write_text(
        WRONG_VOLUME, encoding="utf-8")

    result = run_task(folder, make_runner(), 60)

    assert result.status == FAILED
    assert result.score == 0.8
    assert "volume" in result.error


def test_the_expectation_file_named_by_the_answer_is_used(tmp_path):
    """The expectation file of the answer is the one that judges the part."""
    folder = copy_task(tmp_path)
    (folder / "project" / "expect" / "other.toml").write_text(
        WRONG_VOLUME, encoding="utf-8")

    result = run_task(folder, make_runner(), 60)

    assert result.status == OK
    assert result.score == 1.0
