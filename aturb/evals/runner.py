"""Build the part of one task and score it.

One task folder is one task: the task file names the part, the answer file
holds the correct answer, and the project folder holds the candidate part
file. The runner builds the candidate through the runner contract and judges
the exported STEP against the answer.

The judgement itself lives in ``aturb/evals/judge.py``: the task is judged
once and this module returns the result of that one judgement. The signature,
the five-field result and the scoring rule are the ones of Phase 4 and do not
change.

The build project is always the task's own ``project/`` folder. It is never
passed in, never read from the task file and never taken from the working
directory of the caller.

The answer file stays outside the candidate project and is never handed to
the runner: the runner only ever sees the build request of the contract.

Every failure is a result and never an exception. A task that cannot be
judged is an error result, and a task whose checks did not pass is a failed
result.
"""

from __future__ import annotations

from pathlib import Path

from aturb.contract.runner import Runner
from aturb.evals.judge import judge_task
from aturb.evals.result import TaskResult


def run_task(task_dir: Path, runner: Runner, timeout_s: int) -> TaskResult:
    """Build and score one task folder.

    The task file and the answer file are read first. A task file that cannot
    be read gives an error result whose task ID is the folder name and whose
    part ID is empty; an answer file that cannot be read gives an error result
    whose task ID is the task ID of the task file.

    The part is then built through the runner, the exported STEP is judged
    against the expectation file named by the answer, and the checks are
    scored. A missing project folder, a failed build and a STEP file that
    cannot be read are all error results.

    The result is the result of the one judgement of the task.
    """
    return judge_task(task_dir, runner, timeout_s).result
