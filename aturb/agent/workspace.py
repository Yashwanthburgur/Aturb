"""The scratch task folder that receives the candidate.

The agent never writes into the committed task. It writes into a scratch copy
of the task, made under a work directory, and the Phase 4 evaluator scores that
copy unchanged.

The copy holds the task file, the answer file and the project folders
``expect/`` and ``requirements/``. It never holds the committed
``project/parts/``, so the reference part file never reaches the agent, and it
never holds ``project/out/``, so no build product of an earlier run is reused.
The answer file is copied because the evaluator needs it; the agent never reads
it.

Every path stays inside the work directory. A path that would escape raises
``ValueError``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from aturb.evals.task import load_task
from aturb.workspace.paths import PathEscapeError, resolve_inside

TASK_FILE_NAME = "task.toml"
ANSWER_FILE_NAME = "answer.toml"
PROJECT_DIR_NAME = "project"
PARTS_DIR_NAME = "parts"
COPIED_PROJECT_DIRS = ("expect", "requirements")


def prepare_candidate_task(task_dir: Path, work_dir: Path) -> Path:
    """Copy one task into the work directory and return the scratch folder.

    The scratch folder is ``work_dir/<task_id>/``. It holds the task file, the
    answer file and the project folders ``expect/`` and ``requirements/``, and
    its ``project/parts/`` folder is empty. The committed ``project/parts/`` and
    ``project/out/`` are never copied, so the reference part file never reaches
    the agent.

    A scratch folder that is the task folder itself, or that lies inside it, is
    refused: the committed task is never written to.
    """
    task_dir = Path(task_dir)
    work_dir = Path(work_dir)
    spec = load_task(task_dir)
    scratch = _inside(work_dir, spec.task_id)
    _refuse_task_folder(scratch, task_dir)

    scratch.mkdir(parents=True, exist_ok=True)
    _copy_file(task_dir / TASK_FILE_NAME, scratch / TASK_FILE_NAME)
    _copy_file(task_dir / ANSWER_FILE_NAME, scratch / ANSWER_FILE_NAME)

    project = scratch / PROJECT_DIR_NAME
    project.mkdir(parents=True, exist_ok=True)
    for name in COPIED_PROJECT_DIRS:
        source = task_dir / PROJECT_DIR_NAME / name
        if source.is_dir():
            shutil.copytree(source, project / name, dirs_exist_ok=True)

    parts = project / PARTS_DIR_NAME
    if parts.exists():
        shutil.rmtree(parts)
    parts.mkdir(parents=True)
    return scratch


def candidate_path(project: Path, part_id: str, extension: str) -> Path:
    """Return the path of the candidate file of one part.

    The path is ``project/parts/<part_id>_candidate<extension>``. A part ID or
    an extension that would place the file outside the parts folder raises
    ``ValueError``.
    """
    parts = _inside(Path(project), PARTS_DIR_NAME)
    return _inside(parts, f"{part_id}_candidate{extension}")


def write_candidate(project: Path, part_id: str, extension: str, text: str) -> Path:
    """Write the candidate file of one part and return its path."""
    path = candidate_path(project, part_id, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _inside(root: Path, rel: str | Path) -> Path:
    """Return a path inside root, or raise ValueError when it escapes."""
    try:
        return resolve_inside(root, rel)
    except PathEscapeError as exc:
        raise ValueError(f"the path is outside {root}: {exc}") from exc


def _copy_file(source: Path, target: Path) -> None:
    """Copy one file of the task into the scratch folder."""
    if not source.is_file():
        raise FileNotFoundError(f"the task has no {source.name}: {source}")
    shutil.copy2(source, target)


def _refuse_task_folder(scratch: Path, task_dir: Path) -> None:
    """Refuse a scratch folder that is the task folder or lies inside it."""
    source = task_dir.resolve()
    if scratch == source or scratch.is_relative_to(source):
        raise ValueError(
            f"the scratch folder is inside the task folder: {scratch}")
