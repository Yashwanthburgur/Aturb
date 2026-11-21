"""Run every task folder of a set and return one result per folder.

A task set is a folder of task folders. The batch runs each of them through
the task runner and keeps every result, so the counts of a run always add up.

A malformed task is a result of its own, never a skip and never a reason to
stop the batch: the fallback error result of the task runner is the only
fallback there is.
"""

from __future__ import annotations

from pathlib import Path

from aturb.contract.runner import Runner
from aturb.evals.result import TaskResult
from aturb.evals.runner import run_task


def run_batch(tasks_root: Path, runner: Runner, timeout_s: int) -> list[TaskResult]:
    """Run every task folder of a set and return one result per folder.

    The immediate subfolders of ``tasks_root`` are listed in name order and
    every one of them is run. The list holds exactly one result per folder,
    in the same order, so a malformed task never hides a good one.

    A ``tasks_root`` that does not exist raises the error of the file system:
    that is a mistake of the caller, not a task that failed.
    """
    tasks_root = Path(tasks_root)
    folders = sorted(
        (path for path in tasks_root.iterdir() if path.is_dir()),
        key=lambda path: path.name,
    )
    return [run_task(folder, runner, timeout_s) for folder in folders]
