"""Tests for the scratch task folder of the agent.

The scratch folder is a copy of the committed task without the reference part
file, so the agent cannot read the answer and the committed task stays
untouched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.agent.workspace import (
    candidate_path,
    prepare_candidate_task,
    write_candidate,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"
PART_ID = "plt0001"
EXTENSION = ".py"
TEXT = "# the candidate part\n"


def _files(folder: Path) -> set[str]:
    """Return the relative paths of every file under a folder."""
    return {
        path.relative_to(folder).as_posix()
        for path in folder.rglob("*")
        if path.is_file()
    }


def test_the_scratch_folder_is_named_after_the_task(tmp_path):
    """The scratch folder is the task ID inside the work directory."""
    scratch = prepare_candidate_task(TASK_DIR, tmp_path)

    assert scratch.name == "plate_2holes"
    assert scratch.parent == tmp_path.resolve()


def test_the_scratch_folder_holds_the_task_files(tmp_path):
    """The scratch folder holds the task file, the answer file and the folders."""
    scratch = prepare_candidate_task(TASK_DIR, tmp_path)

    assert (scratch / "task.toml").is_file()
    assert (scratch / "answer.toml").is_file()
    assert (scratch / "project" / "expect" / "plt0001.toml").is_file()
    assert (scratch / "project" / "requirements" / "plt0001.md").is_file()


def test_the_copied_task_file_is_the_committed_one(tmp_path):
    """The copy of the task file is the committed task file."""
    scratch = prepare_candidate_task(TASK_DIR, tmp_path)

    copied = (scratch / "task.toml").read_text(encoding="utf-8")
    committed = (TASK_DIR / "task.toml").read_text(encoding="utf-8")

    assert copied == committed


def test_the_scratch_folder_holds_no_part_file(tmp_path):
    """The scratch folder has an empty parts folder and no reference part."""
    scratch = prepare_candidate_task(TASK_DIR, tmp_path)

    parts = scratch / "project" / "parts"

    assert parts.is_dir()
    assert list(parts.iterdir()) == []


def test_the_scratch_folder_holds_no_output_folder(tmp_path):
    """The scratch folder has no build product of an earlier run."""
    scratch = prepare_candidate_task(TASK_DIR, tmp_path)

    assert not (scratch / "project" / "out").exists()


def test_the_committed_task_is_unchanged(tmp_path):
    """The copy leaves the committed task folder exactly as it was."""
    before = _files(TASK_DIR)

    prepare_candidate_task(TASK_DIR, tmp_path)

    assert _files(TASK_DIR) == before
    assert (TASK_DIR / "project" / "parts" / "plt0001_base_plate.py").is_file()


def test_a_second_preparation_starts_from_an_empty_parts_folder(tmp_path):
    """A scratch folder that is prepared again holds no old candidate."""
    scratch = prepare_candidate_task(TASK_DIR, tmp_path)
    write_candidate(scratch / "project", PART_ID, EXTENSION, TEXT)

    again = prepare_candidate_task(TASK_DIR, tmp_path)

    assert list((again / "project" / "parts").iterdir()) == []


def test_a_scratch_folder_inside_the_task_folder_raises(tmp_path):
    """The committed task folder is never written to."""
    with pytest.raises(ValueError):
        prepare_candidate_task(TASK_DIR, TASK_DIR)


def test_the_candidate_path_is_named_after_the_candidate(tmp_path):
    """The candidate path ends with the candidate name and the extension."""
    path = candidate_path(tmp_path / "project", PART_ID, EXTENSION)

    assert path.name == "plt0001_candidate.py"
    assert path.parent.name == "parts"


def test_the_written_candidate_holds_the_text(tmp_path):
    """The written candidate file holds exactly the text it was given."""
    project = tmp_path / "project"

    path = write_candidate(project, PART_ID, EXTENSION, TEXT)

    assert path.read_text(encoding="utf-8") == TEXT


def test_a_candidate_path_that_escapes_raises(tmp_path):
    """A part ID that climbs out of the parts folder is refused."""
    with pytest.raises(ValueError):
        candidate_path(tmp_path / "project", "../evil", EXTENSION)


def test_a_candidate_path_that_climbs_out_raises(tmp_path):
    """An extension that climbs out of the parts folder is refused."""
    with pytest.raises(ValueError):
        candidate_path(tmp_path / "project", PART_ID, "/../../evil.py")
