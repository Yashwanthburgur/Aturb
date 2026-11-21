"""Tests for the aturb build and aturb check CLI using the stub pack.

The stub pack copies the committed fixture, so the checks of the demo plate
run over that fixture without a CAD.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from aturb.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE_STUB = REPO_ROOT / "tests" / "fixtures" / "conformance" / "stub"
DEMO_EXPECT = REPO_ROOT / "projects" / "demo" / "expect" / "plt0001.toml"
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"


def write_config(tmp_path: Path) -> Path:
    """Write a tmp config with the stub pack active and return its path."""
    config = tmp_path / "aturb.local.toml"
    config.write_text(
        'active_pack = "stub"\n[packs.stub]\n[timeouts]\nbuild_s = 60\n',
        encoding="utf-8",
    )
    return config


def make_project(tmp_path: Path, part_text: str = "stub part file") -> Path:
    """Copy the stub conformance project into tmp_path and return its root."""
    project = tmp_path / "proj"
    shutil.copytree(CONFORMANCE_STUB, project)
    if part_text != "stub part file":
        (project / "parts" / "plt0001_base_plate.stub").write_text(
            part_text, encoding="utf-8")
    return project


def write_expectation(project: Path, text: str | None = None) -> None:
    """Write the expected values of the part into the project.

    The committed expectation file of the demo plate is used by default. The
    stub pack builds the same plate, so the same expected values apply.
    """
    expect_dir = project / "expect"
    expect_dir.mkdir(exist_ok=True)
    if text is None:
        text = DEMO_EXPECT.read_text(encoding="utf-8")
    (expect_dir / "plt0001.toml").write_text(text, encoding="utf-8")


def make_task_set(tmp_path: Path) -> Path:
    """Copy the committed task into a tmp task set and return the set folder."""
    tasks = tmp_path / "tasks"
    tasks.mkdir(exist_ok=True)
    shutil.copytree(TASK_DIR, tasks / "plate_2holes",
                    ignore=shutil.ignore_patterns("out"))
    return tasks


def test_ok_build(tmp_path, capsys):
    """A good build prints a line starting 'ok plt0001' and returns 0."""
    project = make_project(tmp_path)
    code = main(["build", str(project), "plt0001",
                 "--config", str(write_config(tmp_path))])
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("ok plt0001")


def test_scripted_failure(tmp_path, capsys):
    """A scripted timeout prints 'failed plt0001 timeout' and returns 1."""
    project = make_project(tmp_path, part_text="# STUB: fail=timeout")
    code = main(["build", str(project), "plt0001",
                 "--config", str(write_config(tmp_path))])
    out = capsys.readouterr().out
    assert code == 1
    assert out.startswith("failed plt0001 timeout")


def test_malformed_config_returns_2(tmp_path, capsys):
    """A malformed config file prints a clean error and returns 2."""
    config = tmp_path / "broken.toml"
    config.write_text('active_pack = "stub\n', encoding="utf-8")
    project = make_project(tmp_path)

    code = main(["build", str(project), "plt0001", "--config", str(config)])

    out = capsys.readouterr().out
    assert code == 2
    assert "invalid TOML" in out
    assert "Traceback" not in out


def test_missing_config_returns_2(tmp_path, capsys, monkeypatch):
    """A missing config file prints a message and returns 2."""
    monkeypatch.delenv("ATURB_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    project = make_project(tmp_path)
    code = main(["build", str(project), "plt0001"])
    capsys.readouterr()
    assert code == 2


def test_check_passes_on_the_fixture(tmp_path, capsys):
    """Every check passes on the committed fixture and the command returns 0."""
    project = make_project(tmp_path)
    write_expectation(project)
    code = main(["check", str(project), "plt0001",
                 "--config", str(write_config(tmp_path))])
    out = capsys.readouterr().out
    assert code == 0
    assert "check volume passed" in out
    assert "check hole_count passed" in out
    assert "failed" not in out


def test_check_fails_on_a_wrong_expected_value(tmp_path, capsys):
    """A wrong expected value fails one check and the command returns 1."""
    project = make_project(tmp_path)
    wrong = DEMO_EXPECT.read_text(encoding="utf-8").replace(
        "volume = 35214.602", "volume = 1.0")
    write_expectation(project, wrong)
    code = main(["check", str(project), "plt0001",
                 "--config", str(write_config(tmp_path))])
    out = capsys.readouterr().out
    assert code == 1
    assert "check volume failed" in out
    assert "check bbox_x passed" in out


def test_check_without_an_expectation_file_returns_1(tmp_path, capsys):
    """A part with no expected values has no check that can pass."""
    project = make_project(tmp_path)
    code = main(["check", str(project), "plt0001",
                 "--config", str(write_config(tmp_path))])
    out = capsys.readouterr().out
    assert code == 1
    assert "check expectations failed" in out


def test_check_with_a_missing_config_returns_2(tmp_path, capsys, monkeypatch):
    """A missing config file prints a message and returns 2."""
    monkeypatch.delenv("ATURB_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    project = make_project(tmp_path)
    write_expectation(project)
    code = main(["check", str(project), "plt0001"])
    out = capsys.readouterr().out
    assert code == 2
    assert "Traceback" not in out


def test_eval_of_a_good_task_set_returns_0(tmp_path, capsys):
    """A good task set is scored, printed with a summary and returns 0."""
    tasks = make_task_set(tmp_path)

    code = main(["eval", str(tasks), "--config", str(write_config(tmp_path))])

    out = capsys.readouterr().out
    assert code == 0
    assert "task plate_2holes ok score=1.0" in out
    assert "summary tasks=1 passed=1 failed=0 errored=0 score=1.0" in out


def test_eval_of_a_malformed_task_set_returns_1(tmp_path, capsys):
    """A malformed task is printed as an error and the run returns 1."""
    tasks = make_task_set(tmp_path)
    (tasks / "broken").mkdir()

    code = main(["eval", str(tasks), "--config", str(write_config(tmp_path))])

    out = capsys.readouterr().out
    assert code == 1
    assert "task broken error score=0.0" in out
    assert "the task file could not be read" in out
    assert "summary tasks=2 passed=1 failed=0 errored=1 score=0.5" in out


def test_eval_writes_the_result_file_in_the_given_folder(tmp_path, capsys):
    """The run is written to the results folder the command was given."""
    tasks = make_task_set(tmp_path)
    results = tmp_path / "elsewhere"

    code = main(["eval", str(tasks), "--config", str(write_config(tmp_path)),
                 "--results-dir", str(results)])

    capsys.readouterr()
    assert code == 0
    assert len(list(results.glob("*.toml"))) == 1


def test_eval_with_a_malformed_config_returns_2(tmp_path, capsys):
    """A malformed config file prints a clean error and returns 2."""
    config = tmp_path / "broken.toml"
    config.write_text('active_pack = "stub\n', encoding="utf-8")
    tasks = make_task_set(tmp_path)

    code = main(["eval", str(tasks), "--config", str(config)])

    out = capsys.readouterr().out
    assert code == 2
    assert "invalid TOML" in out
    assert "Traceback" not in out
