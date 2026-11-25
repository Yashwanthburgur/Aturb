"""Expectation-free generation with bounded candidate-side build repair."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, replace
from pathlib import Path

from aturb.agent.config import DEFAULTS
from aturb.agent.conventions import check_conventions
from aturb.agent.feedback import BuildFeedback, feedback_text
from aturb.agent.prompt import compose_prompt
from aturb.agent.run import (
    PreparedTask,
    compute_cost_usd,
    estimate_input_tokens,
    run_attempt,
)
from aturb.agent.types import ModelClient
from aturb.contract.runner import Runner
from aturb.contract.types import BuildRequest, FailureKind
from aturb.evals.judge import CandidateGeometry, sanitize_text, summarize_geometry
from aturb.packs import PackManifest
from aturb.verify.step import StepLoadError, load_step

DEFAULT_PART_ID = "part0001"  # starting default
UNREPAIRABLE_FAILURE_KINDS = frozenset(
    {FailureKind.RUNNER_CRASH.value, FailureKind.INPUT_ERROR.value})
PART_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
OUTPUTS = ("native", "step")


@dataclass(frozen=True)
class GenerateResult:
    """The artifacts, measurements and bounded-run outcome of one request."""

    status: str
    part_id: str
    workspace: Path
    part_path: Path | None = None
    step_path: Path | None = None
    native_path: Path | None = None
    build_status: str = ""
    failure_kind: str = ""
    geometry: CandidateGeometry | None = None
    conventions: tuple[str, ...] = ()
    attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    prompt_version: str = ""
    stop_reason: str = ""
    error: str = ""


@dataclass(frozen=True)
class _Bounds:
    max_attempts: int
    total_input: int
    total_output: int
    total_cost: float
    max_output: int
    input_price: float
    output_price: float


def generate_part(
    requirement: str,
    out_dir: Path,
    client: ModelClient,
    runner: Runner,
    settings: dict,
    pack: PackManifest,
    timeout_s: int,
    part_id: str = DEFAULT_PART_ID,
) -> GenerateResult:
    """Generate one part, returning an error result instead of raising."""
    workspace = Path(out_dir)
    try:
        workspace = workspace.resolve()
        return _generate(requirement, workspace, client, runner, settings, pack,
                         timeout_s, part_id)
    except Exception as exc:
        return GenerateResult(
            status="error", part_id=str(part_id), workspace=workspace,
            stop_reason="preparation_error",
            error=f"generation could not be prepared: {sanitize_text(str(exc))}")


def _generate(requirement, workspace, client, runner, settings, pack,
              timeout_s, part_id) -> GenerateResult:
    if not isinstance(requirement, str) or not requirement.strip():
        return _input_error(workspace, part_id, "the requirement is empty")
    if (not isinstance(part_id, str) or not PART_ID_RE.fullmatch(part_id)
            or ".." in part_id or "/" in part_id or "\\" in part_id):
        return _input_error(workspace, part_id, "the part ID is not a safe name")
    try:
        bounds = _limits(settings)
    except (TypeError, ValueError) as exc:
        return _input_error(workspace, part_id, str(exc))
    try:
        pack_prompt = (pack.pack_dir / pack.prompt_dir / "agent.md").read_text(
            encoding="utf-8")
        if not pack_prompt.strip():
            raise ValueError("the pack prompt is empty")
        project = workspace / "project"
        (project / "parts").mkdir(parents=True, exist_ok=True)
        (project / "out").mkdir(parents=True, exist_ok=True)
    except (OSError, UnicodeError, ValueError) as exc:
        return GenerateResult(
            status="error", part_id=part_id, workspace=workspace,
            stop_reason="preparation_error", error=sanitize_text(str(exc)))

    prepared = PreparedTask(
        task_id=part_id, part_id=part_id, scratch=workspace,
        requirement=requirement.strip(), pack_prompt=pack_prompt)
    result = GenerateResult(
        status="error", part_id=part_id, workspace=workspace)

    def finish(status: str, reason: str, error: str = "") -> GenerateResult:
        return replace(result, status=status, stop_reason=reason, error=error)

    calls = input_tokens = output_tokens = 0
    cost_usd = 0.0
    first_version = ""
    feedback = ""
    for attempt in range(1, bounds.max_attempts + 1):
        prompt = compose_prompt(pack_prompt, prepared.requirement, feedback)
        refusal = _budget_error(
            prompt, bounds, input_tokens, output_tokens, cost_usd)
        if refusal:
            return finish("error", "budget_exceeded", refusal)
        outcome = run_attempt(prepared, client, settings,
                              pack, feedback=feedback)
        if outcome.prompt_version:
            calls += 1
            first_version = first_version or outcome.prompt_version
        input_tokens += outcome.input_tokens
        output_tokens += outcome.output_tokens
        cost_usd += outcome.cost_usd
        result = replace(
            result, part_path=outcome.candidate_path or result.part_path,
            attempts=calls, input_tokens=input_tokens, output_tokens=output_tokens,
            cost_usd=cost_usd, prompt_version=first_version)
        if outcome.status != "ok":
            return finish("error", "model_error", outcome.error)

        step_path = native_path = None
        geometry = None
        diagnostics: tuple[str, ...] = ()
        out_part = project / "out" / part_id
        try:
            if out_part.exists():
                shutil.rmtree(out_part, ignore_errors=False)
            out_part.mkdir(parents=True, exist_ok=False)
            request = BuildRequest(
                project_root=str(project), part_id=part_id,
                language=runner.info().language, outputs=OUTPUTS,
                timeout_s=timeout_s)
            build = runner.build(request)
        except Exception as exc:
            build_status = "failed"
            kind = FailureKind.RUNNER_CRASH.value
            build_fb = BuildFeedback(
                status=build_status, failure_kind=kind,
                error_text=sanitize_text(f"the build failed: {exc}"))
        else:
            build_status = build.status
            diagnostics = tuple(
                sanitize_text(f"{key}: {value}")
                for key, value in build.native_diagnostics.items())
            if build.status != "ok":
                kind = (build.failure_kind.value
                        if build.failure_kind is not None else "")
                build_fb = BuildFeedback(
                    status=build.status, failure_kind=kind,
                    error_text=sanitize_text(build.error_text))
            else:
                native_path = _artifact(project, build.artifacts.get("native"))
                candidate = _artifact(project, build.artifacts.get("step"))
                if candidate is None:
                    build_status = "failed"
                    kind = FailureKind.EXPORT_FAILED.value
                    build_fb = BuildFeedback(
                        status="failed", failure_kind=kind,
                        error_text="the build produced no STEP file")
                else:
                    try:
                        model = load_step(candidate)
                    except StepLoadError as exc:
                        build_status = "failed"
                        kind = FailureKind.INVALID_GEOMETRY.value
                        build_fb = BuildFeedback(
                            status="failed", failure_kind=kind,
                            error_text=sanitize_text(
                                f"the STEP file could not be read: {exc}"))
                    else:
                        step_path = candidate
                        geometry = summarize_geometry(model)
                        kind = ""
                        if geometry.is_valid and geometry.is_single_solid:
                            build_fb = BuildFeedback(status="ok")
                        else:
                            build_fb = BuildFeedback(
                                status="ok", failure_kind="",
                                error_text="exported STEP is invalid or not a single solid")
        conventions = tuple(check_conventions(
            part_id, pack.part_extension, outcome.candidate_text))
        result = replace(
            result, step_path=step_path, native_path=native_path,
            build_status=build_status, failure_kind=kind, geometry=geometry,
            conventions=conventions)
        if geometry is not None and geometry.is_valid and geometry.is_single_solid:
            return finish("ok", "built")
        if attempt >= bounds.max_attempts:
            return finish("error", "max_attempts", build_fb.error_text)
        if kind in UNREPAIRABLE_FAILURE_KINDS:
            return finish("error", "unrepairable", build_fb.error_text)
        feedback = feedback_text(
            build_fb, diagnostics=diagnostics, conventions=conventions,
            geometry=geometry, previous_code=outcome.candidate_text)
    return finish("error", "max_attempts", "the generation made no attempt")


def _input_error(workspace: Path, part_id, error: str) -> GenerateResult:
    return GenerateResult(
        status="error", part_id=str(part_id), workspace=workspace,
        stop_reason="settings_error", error=error)


def _limits(settings: dict) -> _Bounds:
    attempts = _number(settings, "max_attempts")
    if attempts < 1 or not attempts.is_integer():
        raise ValueError(
            "the agent setting 'max_attempts' must be a whole number >= 1")
    return _Bounds(
        max_attempts=int(attempts),
        total_input=int(_number(settings, "max_total_input_tokens")),
        total_output=int(_number(settings, "max_total_output_tokens")),
        total_cost=_number(settings, "max_total_cost_usd"),
        max_output=int(_number(settings, "max_output_tokens")),
        input_price=_number(settings, "input_price_per_mtok"),
        output_price=_number(settings, "output_price_per_mtok"))


def _number(settings: dict, key: str) -> float:
    value = settings.get(key, DEFAULTS.get(key, 0))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"the agent setting {key!r} must be a number")
    if value < 0:
        raise ValueError(f"the agent setting {key!r} cannot be negative")
    return float(value)


def _budget_error(prompt: str, bounds: _Bounds, used_input: int,
                  used_output: int, used_cost: float) -> str:
    estimated = estimate_input_tokens(prompt)
    if used_input + estimated > bounds.total_input:
        return (f"the cumulative input token budget would be passed: "
                f"{used_input + estimated} tokens > {bounds.total_input}")
    if used_output + bounds.max_output > bounds.total_output:
        return (f"the cumulative output token budget would be passed: "
                f"{used_output + bounds.max_output} tokens > {bounds.total_output}")
    if bounds.input_price > 0.0 or bounds.output_price > 0.0:
        cost = compute_cost_usd(
            estimated, bounds.max_output, bounds.input_price, bounds.output_price)
        if used_cost + cost > bounds.total_cost:
            return (f"the cumulative cost budget would be passed: "
                    f"{used_cost + cost:.6f} USD > {bounds.total_cost:.6f} USD")
    return ""


def _artifact(project: Path, relative: str | None) -> Path | None:
    if not relative:
        return None
    try:
        path = (project / relative).resolve()
        if not path.is_relative_to(project) or not path.is_file():
            return None
    except (OSError, ValueError):
        return None
    return path
