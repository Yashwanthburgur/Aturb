"""Judge one task once, and report what the candidate itself measures.

The evaluator judges a task: it builds the candidate, reads the exported STEP,
compares the geometry with the expectation file and scores the task. This
module holds that judgement and the candidate-only geometry summary that goes
with it.

The summary is measured from the exported STEP of the candidate alone, with the
neutral readers of the core. It holds no expected value, no tolerance, no check
name and no verdict, so it cannot say whether the candidate is right.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from aturb.contract.runner import Runner
from aturb.contract.types import BuildRequest, BuildResult
from aturb.evals.answer import load_answer
from aturb.evals.result import TaskResult
from aturb.evals.scoring import score_task, task_status
from aturb.evals.task import load_task
from aturb.verify.expectations import (
    checks_from_expectations,
    load_expectations,
)
from aturb.verify.holes import find_holes
from aturb.verify.step import StepLoadError, StepModel, load_step

PROJECT_DIR_NAME = "project"
OUTPUTS = ("native", "step")

# A quoted absolute path: a Windows path with a drive letter or a POSIX path.
_QUOTED_PATH = re.compile(r'"((?:[A-Za-z]:[\\/]|/)[^"]+)"')
# An absolute Windows path: a drive letter and a separator.
_WINDOWS_PATH = re.compile(r"\b[A-Za-z]:[\\/][^\s\"'<>|]*")
# An absolute POSIX path: a separator and at least one segment.
_POSIX_PATH = re.compile(r"(?<![\w./:-])/(?:[\w.+-]+/)*[\w.+-]+")


@dataclass(frozen=True)
class HoleSummary:
    """One hole of the candidate, in neutral terms.

    The position is the point on the hole axis at the middle of the hole along
    that axis, as X and Y.
    """

    diameter: float
    x: float
    y: float


@dataclass(frozen=True)
class CandidateGeometry:
    """What the candidate itself measures, read from its exported STEP.

    The summary holds no expected value, no tolerance, no check name and no
    verdict: it says what the candidate measures, never what it should measure.
    """

    is_valid: bool
    is_single_solid: bool
    volume: float
    bbox_size: tuple[float, float, float]
    holes: tuple[HoleSummary, ...]


@dataclass(frozen=True)
class TaskJudgement:
    """The judgement of one task: its result and what the candidate measured.

    ``geometry`` is ``None`` when no STEP file could be read. ``build_status``
    and ``failure_kind`` are empty when the runner was never reached.
    ``error_text`` is the sanitized build error text and ``diagnostics`` holds
    the sanitized informational diagnostics.
    """

    result: TaskResult
    geometry: CandidateGeometry | None
    build_status: str
    failure_kind: str
    error_text: str
    diagnostics: tuple[str, ...]


def summarize_geometry(model: StepModel) -> CandidateGeometry:
    """Measure the candidate-only summary of a loaded STEP model.

    Every field is measured from the model itself: nothing is read from an
    expectation file and no check result is touched.
    """
    size = model.bbox_size
    holes = tuple(
        HoleSummary(diameter=hole.diameter, x=hole.x, y=hole.y)
        for hole in find_holes(model)
    )
    return CandidateGeometry(
        is_valid=model.is_valid,
        is_single_solid=model.is_single_solid,
        volume=model.volume,
        bbox_size=(size.X, size.Y, size.Z),
        holes=holes,
    )


def sanitize_text(text: str) -> str:
    """Remove the absolute paths of a text, keeping the file names and the text.

    A Windows path with a drive letter and a POSIX absolute path are replaced
    by the name of the file they point at, so the text still says which file
    failed and on which line, without saying where the machine put it.
    """
    if not text:
        return text
    cleaned = _QUOTED_PATH.sub(_replace_quoted, text)
    cleaned = _WINDOWS_PATH.sub(_replace_path, cleaned)
    return _POSIX_PATH.sub(_replace_path, cleaned)


def judge_task(task_dir: Path, runner: Runner, timeout_s: int) -> TaskJudgement:
    """Judge one task folder once.

    The task file and the answer file are read first, the part is built through
    the runner, the exported STEP is judged against the expectation file named
    by the answer, and the checks are scored. Every failure is a result and
    never an exception.

    The judgement holds the result of the task, the candidate-only geometry
    summary, the build status, the failure kind, the sanitized build error text
    and the informational diagnostics of the build.
    """
    task_dir = Path(task_dir)
    try:
        spec = load_task(task_dir)
    except (OSError, ValueError) as exc:
        return _judgement(TaskResult.from_error(
            task_dir.name, "", f"the task file could not be read: {exc}"))
    try:
        answer = load_answer(task_dir)
    except (OSError, ValueError) as exc:
        return _judgement(TaskResult.from_error(
            spec.task_id, spec.part_id,
            f"the answer file could not be read: {exc}"))

    project = (task_dir / PROJECT_DIR_NAME).resolve()
    if not project.is_dir():
        return _judgement(TaskResult.from_error(
            spec.task_id, spec.part_id,
            f"the task has no project folder: {project}"))

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
        text = f"the build failed: {exc}"
        return _judgement(
            TaskResult.from_error(spec.task_id, spec.part_id, text),
            error_text=sanitize_text(text))

    status = build.status
    kind = build.failure_kind.value if build.failure_kind is not None else ""
    error_text = sanitize_text(build.error_text)
    diagnostics = _diagnostics(build.native_diagnostics)

    if build.status != "ok":
        return _judgement(
            TaskResult.from_error(
                spec.task_id, spec.part_id,
                build.error_text or "the build failed"),
            build_status=status,
            failure_kind=kind,
            error_text=error_text,
            diagnostics=diagnostics)

    # The candidate-only summary is measured from the exported STEP of the
    # candidate alone, so it is read before the expectation file and it does
    # not depend on it.
    model, step_error = _load_model(project, build)
    geometry = summarize_geometry(model) if model is not None else None

    try:
        expected = load_expectations(project / answer.expect_file)
    except (OSError, ValueError) as exc:
        return _judgement(
            TaskResult.from_error(
                spec.task_id, spec.part_id,
                f"the expectation file could not be read: {exc}"),
            geometry=geometry,
            build_status=status,
            diagnostics=diagnostics)

    if model is None:
        return _judgement(
            TaskResult.from_error(spec.task_id, spec.part_id, step_error),
            build_status=status,
            diagnostics=diagnostics)

    checks = checks_from_expectations(model, expected)
    score, score_error = score_task(answer, checks)
    result = TaskResult(
        task_id=spec.task_id,
        part_id=spec.part_id,
        status=task_status(answer, checks),
        score=score,
        error=score_error,
    )
    return _judgement(
        result,
        geometry=geometry,
        build_status=status,
        diagnostics=diagnostics)


def _load_model(project: Path, build: BuildResult) -> tuple[StepModel | None, str]:
    """Load the exported STEP of the candidate, or say why it could not be read.

    The error text is empty when the model was loaded, and it says why it could
    not be when the model is missing.
    """
    step_rel = build.artifacts.get("step")
    if not step_rel:
        return None, "the build produced no STEP file"
    try:
        return load_step(project / step_rel), ""
    except StepLoadError as exc:
        return None, f"the STEP file could not be read: {exc}"


def _judgement(
    result: TaskResult,
    geometry: CandidateGeometry | None = None,
    build_status: str = "",
    failure_kind: str = "",
    error_text: str = "",
    diagnostics: tuple[str, ...] = (),
) -> TaskJudgement:
    """Build a judgement around the result of a task."""
    return TaskJudgement(
        result=result,
        geometry=geometry,
        build_status=build_status,
        failure_kind=failure_kind,
        error_text=error_text,
        diagnostics=diagnostics,
    )


def _diagnostics(native_diagnostics: dict) -> tuple[str, ...]:
    """Return the informational diagnostics of a build as plain strings."""
    return tuple(
        sanitize_text(f"{key}: {value}")
        for key, value in native_diagnostics.items()
    )


def _replace_quoted(match: re.Match[str]) -> str:
    """Replace a quoted absolute path by the name of its file."""
    return f'"{_file_name(match.group(1))}"'


def _replace_path(match: re.Match[str]) -> str:
    """Replace an absolute path by the name of its file."""
    return _file_name(match.group(0))


def _file_name(path: str) -> str:
    """Return the name of the file a path points at, without its directories."""
    parts = [part for part in re.split(r"[\\/]", path) if part]
    return parts[-1] if parts else "<path>"
