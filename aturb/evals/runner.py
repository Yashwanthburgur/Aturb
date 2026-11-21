"""Build the part of one task and score it.

One task folder is one task: the task file names the part, the answer file
holds the correct answer, and the project folder holds the candidate part
file. The runner builds the candidate through the runner contract and judges
the exported STEP against the answer.

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
from aturb.contract.types import BuildRequest
from aturb.evals.answer import load_answer
from aturb.evals.result import TaskResult
from aturb.evals.scoring import score_task, task_status
from aturb.evals.task import load_task
from aturb.verify.expectations import (
    checks_from_expectations,
    load_expectations,
)
from aturb.verify.step import StepLoadError, load_step

PROJECT_DIR_NAME = "project"
OUTPUTS = ("native", "step")


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
    """
    task_dir = Path(task_dir)
    try:
        spec = load_task(task_dir)
    except (OSError, ValueError) as exc:
        return TaskResult.from_error(
            task_dir.name, "", f"the task file could not be read: {exc}")
    try:
        answer = load_answer(task_dir)
    except (OSError, ValueError) as exc:
        return TaskResult.from_error(
            spec.task_id, spec.part_id,
            f"the answer file could not be read: {exc}")

    project = (task_dir / PROJECT_DIR_NAME).resolve()
    if not project.is_dir():
        return TaskResult.from_error(
            spec.task_id, spec.part_id,
            f"the task has no project folder: {project}")

    request = BuildRequest(
        project_root=str(project),
        part_id=spec.part_id,
        language=runner.info().language,
        outputs=OUTPUTS,
        timeout_s=timeout_s,
    )
    try:
        build = runner.build(request)
    except Exception as exc:
        return TaskResult.from_error(
            spec.task_id, spec.part_id, f"the build failed: {exc}")
    if build.status != "ok":
        return TaskResult.from_error(
            spec.task_id, spec.part_id,
            build.error_text or "the build failed")

    try:
        expected = load_expectations(project / answer.expect_file)
    except (OSError, ValueError) as exc:
        return TaskResult.from_error(
            spec.task_id, spec.part_id,
            f"the expectation file could not be read: {exc}")

    step_rel = build.artifacts.get("step")
    if not step_rel:
        return TaskResult.from_error(
            spec.task_id, spec.part_id, "the build produced no STEP file")
    try:
        model = load_step(project / step_rel)
    except StepLoadError as exc:
        return TaskResult.from_error(
            spec.task_id, spec.part_id,
            f"the STEP file could not be read: {exc}")

    checks = checks_from_expectations(model, expected)
    score, error_text = score_task(answer, checks)
    return TaskResult(
        task_id=spec.task_id,
        part_id=spec.part_id,
        status=task_status(answer, checks),
        score=score,
        error=error_text,
    )
